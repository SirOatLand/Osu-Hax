import time
import cv2
import numpy as np
import pyautogui
import math

from windows_capture import WindowsCapture, Frame, InternalCaptureControl
from imgdiff import detect_imgdiff
from save_image import save_image
from osu_input import *
from read_map import *
from config import SECOND_MONITOR

latest_frame = None
current_action = None

capture = WindowsCapture(
    cursor_capture=None,
    draw_border=None,
    monitor_index=1,
    window_name="osu!",
)

def frame_to_numpy(frame: Frame):
    buf = frame.frame_buffer
    return cv2.cvtColor(buf, cv2.COLOR_BGRA2BGR)

@capture.event
def on_frame_arrived(frame: Frame, capture_control: InternalCaptureControl):
    global latest_frame
    latest_frame = frame

@capture.event 
def on_closed():
    print("Capture Session Closed")
    cv2.destroyAllWindows()

def main(save_image_mode, song_path):
    global start_time
    global osu_index
    global current_action
    global timing_points
    global slider_multiplier

    capture.start_free_threaded()
    screenshot = None

    osu_objects, timing_points, slider_multiplier, time_delay_300 = prep_osu_objects(song_path)
    osu_index = 0
    current_action = None

    osu_start_x, osu_start_y  = osu_to_screen(320, 170)
    pyautogui.moveTo(osu_start_x, osu_start_y)
    pyautogui.mouseDown()
    pyautogui.mouseUp()

    wait_for_title_change()
    while True:
        left_click = ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000
        shift_pressed = ctypes.windll.user32.GetAsyncKeyState(0x10) & 0x8000
        if left_click & shift_pressed:
            start_time = osu_objects[0].time/1000
            osu_index += 1
            break
        else:
            pass

    initial_timestamp = time.perf_counter()
    while True:
        loop_start = time.time()
        if latest_frame is not None:
            screenshot = frame_to_numpy(latest_frame)

            # ============= Save Image Mode =============
            if save_image_mode:
                save_image(screenshot, folder_names=['img1', 'img2', 'img3', 'img4'], img_count=250, delay=0.2)
                cv2.imshow("screenshoting", screenshot)

            # ============= Normal Capture =============
            else:
                cv2.imshow("Fake Osu", screenshot)
                pass


        # ============= Osu Input =============
        now_t = time.perf_counter() + start_time - initial_timestamp
        obj = osu_objects[osu_index]
        if current_action is None:
            print(
                f"OBJ={obj}, curr_time={now_t:.5f}, time={(obj.time/1000):.5f}, index={osu_index}",
            )
            pass
            if now_t >= (obj.time / 1000):
                if isinstance(obj, HitCircle):
                    current_action = CircleAction(obj)

                elif isinstance(obj, Slider):
                    current_action = SliderAction(obj)

                elif isinstance(obj, Spinner):
                    current_action = SpinnerAction(obj)
        
        if current_action is not None:
            current_action.update(now_t)
            if current_action.done:
                current_action = None
                osu_index += 1
        
        # ============= FPS Counter =============
        key = cv2.waitKey(1)
        if key == ord('f') or (ctypes.windll.user32.GetAsyncKeyState(0x46) & 0x0001):
            try:
                print("FPS:", 1 / (time.time() - loop_start))
            except ZeroDivisionError:
                pass

        # ============= Exit =============
        if key == ord('q') or (ctypes.windll.user32.GetAsyncKeyState(0x51) & 0x0001):
            # cv2.destroyAllWindows()
            break

if __name__ == "__main__":
    # pyautogui.PAUSE = 0.05
    main(save_image_mode=False, song_path="./test_songs/cin_oat.osu")
