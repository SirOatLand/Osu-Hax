from collections import deque
import time
import math

class CoordQueue:
    def __init__(self, threshold=25, cooldown_time=0.2):
        self.queue = deque()
        self.threshold = threshold
        self.cooldown_time = cooldown_time   # seconds
        self.cooldown = []  # list of (x, y, cls, expire_time)

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
        for (qx, qy, qcls) in self.queue:
            if qcls == cls and self._same((x, y), (qx, qy)):
                return False

        # 3. Add normally
        self.queue.append((x, y, cls))
        print(f"[Queue] Added: ({x}, {y}, {cls})  size={len(self.queue)}")
        return True

    # -------------------------------
    # Pop the next item of given class
    # -------------------------------
    def pop(self, cls):
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

    # -------------------------------
    # Manual removal (optional)
    # -------------------------------
    def remove(self, x, y, cls):
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
