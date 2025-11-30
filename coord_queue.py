from collections import deque
import time
import math
from config import *
from osu_input import ai_to_screen


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


class CoordQueue:
    def __init__(self, threshold=25, cooldown_time=0.2, min_detect_count=5):
        self.queue = deque()
        self.threshold = threshold
        self.cooldown_time = cooldown_time   # seconds
        self.cooldown = []  # list of (x, y, cls, expire_time)
        self.min_detect_count = min_detect_count  # how many frames required
        self.detect_counts = {}  # store repeated detections

    # -------------------------------
    # Helper: same coord detection
    # -------------------------------
    def _same(self, p1, p2):
        (x1, y1) = p1
        (x2, y2) = p2
        return math.hypot(x1 - x2, y1 - y2) <= self.threshold

    # -------------------------------
    # Remove expired cooldown entries
    # -------------------------------
    def _cleanup_cooldown(self):
        now = time.time()
        self.cooldown = [c for c in self.cooldown if c[3] > now]

    # -------------------------------
    # Check if coord is in cooldown
    # -------------------------------
    def _is_in_cooldown(self, x, y, cls):
        now = time.time()
        for (cx, cy, ccls, expire) in self.cooldown:
            if ccls == cls and self._same((x, y), (cx, cy)) and expire > now:
                return True
        return False

    # -------------------------------
    # Add coordinate (with cooldown check)
    # -------------------------------
    def add(self, x, y, cls):
        self._cleanup_cooldown()

        # 1. Check cooldown
        if self._is_in_cooldown(x, y, cls):
            return False

        # 2. Check if already in queue
        for (qx, qy, qcls, qtime) in self.queue:
            if qcls == cls and self._same((x, y), (qx, qy)):
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
        ntime = time.perf_counter()
        self.queue.append((x, y, cls, ntime))
        # print(f"[Queue] Added: ({x}, {y}, {cls}), time={ntime},  size={len(self.queue)}")
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

                print(f"[Queue] Popped: ({qx}, {qy}, {cls}, {ntime})")
                return (qx, qy, cls, ntime)

        return (250, 250, 'none', 0)

    def peek(self, cls):
        for (qx, qy, qcls, ntime) in self.queue:
            if qcls == cls:
                # return without modifying queue
                return (qx, qy, qcls, ntime)

        # Same behavior as your pop() fallback
        return (250, 250, 'none', 0)

    # -------------------------------
    # Manual removal (optional)
    # -------------------------------
    def remove(self, x, y, cls, ntime):
        for i, (qx, qy, qcls, ntime) in enumerate(self.queue):
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
