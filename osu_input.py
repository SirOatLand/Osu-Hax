import pyautogui
import ctypes
from config import *
from read_map import *
import time
import win32gui

global screen_w, screen_h
screen_w, screen_h = pyautogui.size()
screen_w = screen_w + SECOND_MONITOR


def set_cursor(x, y):
    ctypes.windll.user32.SetCursorPos(x, y)
    print(x, y)

def mouse_leftdown():
    ctypes.windll.user32.mouse_event(MOUSE_LEFTDOWN,0,0,0,0)

def mouse_leftup():
    ctypes.windll.user32.mouse_event(MOUSE_LEFTUP,0,0,0,0)

def is_time(ms, start_time):
    target = ms / 1000
    now = time.perf_counter()
    return (now - start_time) >= target

def find_osu_window():
    result = [None]  # store hwnd in a mutable list
    
    def callback(hwnd, _):
        title = win32gui.GetWindowText(hwnd)
        if title.startswith("osu!"):
            result[0] = hwnd

    win32gui.EnumWindows(callback, None)
    return result[0]

def get_osu_client_rect():
        hwnd_osu = find_osu_window()
    
        # left, top, right, bottom in client coordinates
        left, top, right, bottom = win32gui.GetClientRect(hwnd_osu)

        # convert top-left & bottom-right to absolute screen coords
        tl = win32gui.ClientToScreen(hwnd_osu, (left, top))
        br = win32gui.ClientToScreen(hwnd_osu, (right, bottom))

        return tl[0], tl[1], br[0], br[1]


def osu_to_screen(osu_x, osu_y):
    # Get CLIENT RECT (width & height)
    left, top, right, bottom = get_osu_client_rect()
    osu_w = right - left
    osu_h = bottom - top

    # Compute playfield size
    play_h = 0.8 * osu_h
    play_w = (4 / 3) * play_h

    # Center horizontally, center vertically, then apply 2% downward offset
    play_left = (osu_w - play_w) / 2
    play_top  = (osu_h - play_h) / 2 + play_h * 0.02

    # Scale factor
    osu_scale = play_h / 384  # = play_w / 512

    # Final position inside client → convert to screen space
    screen_x = int(osu_x * osu_scale + play_left + left)
    screen_y = int(osu_y * osu_scale + play_top  + top)

    return screen_x, screen_y


def wait_for_title_change(timeout=5):
    hwnd = find_osu_window()

    start_title = win32gui.GetWindowText(hwnd)
    print(f"[INFO] Initial title: {start_title}")

    start_time = time.time()

    while time.time() - start_time < timeout:
        new_title = win32gui.GetWindowText(hwnd)
        if new_title != start_title:
            print(f"[INFO] Title changed!")
            print(f"[INFO] New title: {new_title}")
            return new_title
        time.sleep(0.01)  # 10 ms polling, very accurate

    print("[WARN] Timeout waiting for title change.")
    return None

class CircleAction:
    def __init__(self, obj):
        self.obj = obj
        self.done = False
        self.type = 1

    def update(self, t):
        if not self.done:
            x, y = osu_to_screen(self.obj.x, self.obj.y)
            set_cursor(x, y)
            mouse_leftdown()
            mouse_leftup()
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
        set_cursor(sx, sy)

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

        set_cursor(sx, sy)
        self.angle += 0.35

    

