import pyautogui
from config import SECOND_MONITOR
from read_map import *

global screen_w, screen_h
screen_w, screen_h = pyautogui.size()
screen_w = screen_w + SECOND_MONITOR

def offset_moveTo(x, y, duration):
    x = x + SECOND_MONITOR
    pyautogui.moveTo(x, y, duration)

def is_time(ms, start_time):
    target = ms / 1000
    now = time.perf_counter()
    return (now - start_time) >= target

def osu_to_screen(x, y):
    osu_width = 512
    osu_height = 384
    
    sx = int(x / osu_width * screen_w)
    sy = int(y / osu_height * screen_h)

    return sx, sy

class CircleAction:
    def __init__(self, obj):
        self.obj = obj
        self.done = False
        self.type = 1

    def update(self, t):
        if not self.done:
            x, y = osu_to_screen(self.obj.x, self.obj.y)
            offset_moveTo(x, y, duration=0)
            pyautogui.mouseDown()
            pyautogui.mouseUp()
            self.done = True
    
class SliderAction:
    def __init__(self, obj, timing_point, sv, slider_multiplier):
        self.obj = obj
        self.done = False
        self.type = 2

        beat_length = timing_point.beat_length
        
        px_per_beat = slider_multiplier * 100 * sv
        beats = obj.length / px_per_beat
        
        self.duration = beats * beat_length * obj.slides
        self.endTime = obj.time + self.duration

        # path
        self.curve = [(obj.x, obj.y)] + obj.points

    def update(self, t):
        if self.done:
            return
        
        start_t = self.obj.time / 1000
        end_t   = self.endTime / 1000

        progress = (t - start_t) / (end_t - start_t)
        progress = max(0, min(progress, 1))

        idx = int(progress * (len(self.curve) - 1))
        px, py = self.curve[idx]

        sx, sy = osu_to_screen(px, py)
        offset_moveTo(sx, sy, duration=0)

        if progress >= 1:
            self.done = True

class SpinnerAction:
    def __init__(self, obj):
        self.obj = obj
        self.done = False
        self.type = 8

        self.end_t = obj.endTime / 1000
        self.angle = 0

    def update(self, t):
        if t >= self.end_t:
            self.done = True
            return

        cx, cy = osu_to_screen(self.obj.x, self.obj.y)
        r = 150

        sx = cx + r * math.cos(self.angle)
        sy = cy + r * math.sin(self.angle)

        offset_moveTo(sx, sy, duration=0)
        self.angle += 0.35

    

