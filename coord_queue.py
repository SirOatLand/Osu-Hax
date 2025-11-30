from collections import deque
import time
import math
from osu_input import get_osu_client_rect

def ai_to_screen(ai_x, ai_y, image_width, image_height):
    left, top, right, bottom = get_osu_client_rect()
    osu_width = right - left
    osu_height = bottom - top

    # scale from screenshot → osu window
    screen_x = left + (ai_x / image_width) * osu_width
    screen_y = top + (ai_y / image_height) * osu_height

    return int(screen_x), int(screen_y)

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

    def get_osu_coords(self):
        screen_x, screen_y = ai_to_screen(self.x, self.y, self.screen_x, self.screen_y) 
        osu_x, osu_y  = screen_to_osu(screen_x, screen_y) 
        return osu_x, osu_y

class CoordQueue:
    def __init__(self, threshold_dist=25, threshold_t=300,  cooldown_time=0.2):
        self.queue = deque()
        self.threshold_dist = threshold_dist
        self.threshold_t = threshold_t
        self.cooldown_time = cooldown_time   # seconds
        self.cooldown = []  # list of (x, y, cls, expire_time)

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

        # 3. Add normally
        self.queue.append(data_ai)
        print(f"[Queue] Added: ({x}, {y}, {cls}, {time_ms})  size={len(self.queue)}")
        return True

    # -------------------------------
    # Pop the next item of given class
    # -------------------------------
    def pop(self, data_ai: DataAI):
        cls = data_ai.cls
        for i, (qx, qy, qcls) in enumerate(self.queue):
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
                print(f"[Queue] Force-removed: {removed}")
                return True
        return False

    def __len__(self):
        return len(self.queue)

    def debug(self):
        print("Queue =", list(self.queue))
        print("Cooldown =", self.cooldown)