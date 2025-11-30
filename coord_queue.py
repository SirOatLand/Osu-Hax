from collections import deque
import math


class CoordQueue:
    def __init__(self, threshold=25):
        self.queue = deque()
        self.threshold = threshold

    def _same(self, p1, p2):
        (x1, y1) = p1
        (x2, y2) = p2
        return math.hypot(x1 - x2, y1 - y2) <= self.threshold

    def add(self, x, y, cls):
        for (qx, qy, qcls) in self.queue:
            if qcls == cls and self._same((x, y), (qx, qy)):
                return False  # already in queue
        self.queue.append((x, y, cls))
        print(f"[Queue] Added: ({x}, {y}, {cls})  size={len(self.queue)}")
        return True

    def pop(self, cls):
        for i, (qx, qy, qcls) in enumerate(self.queue):
            if qcls == cls:
                # remove all before + the item
                for _ in range(i + 1):
                    removed = self.queue.popleft()

                print(f"[Queue] Popped: ({qx}, {qy}, {cls})")
                return (qx, qy, cls)

        return None  # nothing found

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
