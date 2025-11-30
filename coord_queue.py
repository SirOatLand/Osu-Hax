from collections import deque
import time
import math
from config import *
from osu_input import ai_to_screen
from osu_input import get_osu_client_rect

def ai_to_screen(ai_x, ai_y, image_width, image_height):
    left, top, right, bottom = get_osu_client_rect()
    osu_width = right - left
    osu_height = bottom - top

    # scale from screenshot → osu window
    screen_x = left + (ai_x / image_width) * osu_width
    screen_y = top + (ai_y / image_height) * osu_height
    return int(screen_x), int(screen_y)

def infer_to_queue(results, coord_queue, image_x, image_y):
    for pred in results.predictions:
        cls_name = pred.class_name
        conf = pred.confidence
        x = pred.x
        y = pred.y
        
    # 1. Filter by class
    if cls_name not in {"circle", "slider_head"}:
        continue

    # 2. Filter by confidence threshold
    if conf < OBJ_MIN_CONFIDENCE:
        continue

    # 3. Convert coordinates to screen space
    x, y = ai_to_screen(x, y, image_x, image_y)

    # 4. Add to queue with timestamp and ar_delay
    coord_queue.add(x, y, cls_name)

def screen_to_osu(screen_x, screen_y):
    # Get CLIENT RECT
    left, top, right, bottom = get_osu_client_rect()
    osu_w = right - left
    osu_h = bottom - top

    # Compute playfield size
    play_h = 0.8 * osu_h
    play_w = (4 / 3) * play_h

    # Centering + 2% vertical offset (same as forward)
    play_left = (osu_w - play_w) / 2
    play_top  = (osu_h - play_h) / 2 + play_h * 0.02

    # osu px → screen px scale
    osu_scale = play_h / 384   # equivalent to play_w / 512

    # Reverse the transform
    osu_x = (screen_x - play_left - left) / osu_scale
    osu_y = (screen_y - play_top  - top) / osu_scale

    return int(osu_x), int(osu_y)

def find_disappeared_coords(old_list, new_list, thresh=30):
    disappeared = []
    for (ox, oy, ocls) in old_list:
        found = False
        for (nx, ny, ncls) in new_list:
            # same class AND close coordinate → still present
            if ncls == ocls and math.hypot(nx - ox, ny - oy) <= thresh:
                found = True
                break
        if not found:
            disappeared.append((ox, oy, ocls))
    return disappeared

class DataAI:
    def __init__(self, obj):
        self.cls = obj['class']
        self.x = obj['x']
        self.y = obj['y']
        self.screen_x = obj['screen_x']
        self.screen_y = obj['screen_y']
        self.width = obj['width']
        self.height = obj['height']
        self.time_ms = obj['time_ms']
        self.time_pf = time.perf_counter()

    def get_osu_coords(self):
        screen_x, screen_y = ai_to_screen(self.x, self.y, self.screen_x, self.screen_y) 
        osu_x, osu_y  = screen_to_osu(screen_x, screen_y) 
        return osu_x, osu_y
    
class CoordQueue:
    def __init__(self, threshold_dist=25,  cooldown_time=0.2, min_detect_count=5, threshold_t=1200):
        self.queue = deque()
        self.threshold_dist = threshold_dist
        self.threshold_t = threshold_t
        self.cooldown_time = cooldown_time   # seconds
        self.cooldown = []  # list of (x, y, cls, expire_time)
        self.min_detect_count = min_detect_count  # how many frames required
        self.detect_counts = {}  # store repeated detections

    # -------------------------------
    # Helper: same coord and time detection
    # -------------------------------
    def _same_dist(self, data_ai_1: DataAI, data_ai_2: DataAI):
        (x1, y1) = data_ai_1.x, data_ai_1.y
        (x2, y2) = data_ai_2.x, data_ai_2.y
        return math.hypot(x1 - x2, y1 - y2) <= self.threshold_dist
    
    def _same_time(self, data_ai_1: DataAI, data_ai_2: DataAI):
        t1 = data_ai_1.time_ms
        t2 = data_ai_2.time_ms
        return abs(t1 - t2) <= self.threshold_t

    # -------------------------------
    # Remove expired cooldown entries
    # -------------------------------
    def _cleanup_cooldown(self):
        now = time.time()
        self.cooldown = [c for c in self.cooldown if c[3] > now]

    # -------------------------------
    # Check if coord is in cooldown
    # -------------------------------
    def _is_in_cooldown(self, data_ai: DataAI):
        now = time.time()
        x, y, cls = data_ai.x, data_ai.y, data_ai.cls
        for (cx, cy, ccls, expire) in self.cooldown:
            if ccls == cls and self._same((x, y), (cx, cy)) and expire > now:
                return True
        return False

    # -------------------------------
    # Add coordinate (with cooldown check)
    # -------------------------------
    def add(self, data_ai: DataAI):
        self._cleanup_cooldown()
        x, y, cls = data_ai.x, data_ai.y, data_ai.cls
        time_ms = data_ai.time_ms
        # 1. Check cooldown
        if self._is_in_cooldown(data_ai):
            return False

        # 2. Check if already in queue
        for data_ai_q in self.queue:
            if data_ai.cls == cls:
                if self._same_time(data_ai, data_ai_q):
                    return False
                
        # Increment detection count
        key = (x, y, cls)
        if key not in self.detect_counts:
            self.detect_counts[key] = 1
        else:
            self.detect_counts[key] += 1

        # Not enough detections yet → ignore
        if self.detect_counts[key] < self.min_detect_count:
            return False
        
        # 3. Add normally
        self.queue.append(data_ai)
        print(f"[Queue] Added: ({x}, {y}, {cls}, {time_ms})  size={len(self.queue)}")
        return True

    # -------------------------------
    # Pop the next item of given class
    # -------------------------------
    def pop(self, cls):
        for i, (qx, qy, qcls, ntime) in enumerate(self.queue):
            if qcls == cls:

                # remove all items before + the matched one
                for _ in range(i + 1):
                    removed = self.queue.popleft()

                # add popped coord to cooldown list
                expire_time = time.time() + self.cooldown_time
                self.cooldown.append((qx, qy, cls, expire_time))

                print(f"[Queue] Popped: ({qx}, {qy}, {cls})")
                return (qx, qy, cls)

        return (250, 250, 'none')

    def peek(self, data_ai: DataAI):
        cls = data_ai.cls
        for (qx, qy, qcls) in self.queue:
            if qcls == cls:
                # return without modifying queue
                return (qx, qy, qcls)

        # Same behavior as your pop() fallback
        return (250, 250, 'none')

    # -------------------------------
    # Manual removal (optional)
    # -------------------------------
    def remove(self, data_ai):
        x, y, cls = data_ai.x, data_ai.y, data_ai.cls
        for i, (qx, qy, qcls) in enumerate(self.queue):
            if qcls == cls and self._same((x, y), (qx, qy)):
                removed = self.queue[i]
                del self.queue[i]
                # add popped coord to cooldown list
                expire_time = time.time() + self.cooldown_time
                self.cooldown.append((qx, qy, cls, expire_time))
                print(f"[Queue] Force-removed: {removed}")
                return True
        return False

    def __len__(self):
        return len(self.queue)

    def debug(self):
        print("Queue =", list(self.queue))
        print("Cooldown =", self.cooldown)