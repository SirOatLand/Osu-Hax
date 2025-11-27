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
    
    start_time = time.perf_counter()
    capture.start_free_threaded()
    screenshot = None

    osu_objects, timing_points, slider_multiplier = prep_osu_objects(song_path)
    osu_index = 0
    current_action = None
    
    print(osu_objects)

    pyautogui.moveTo(1800 + SECOND_MONITOR, 500)
    pyautogui.mouseDown()
    pyautogui.mouseUp()
    time.sleep(3)
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
                pass
                # cv2.imshow("Fake Osu", screenshot)


        # ============= Osu Input =============
        now_t = time.perf_counter() - start_time
        obj = osu_objects[osu_index]
        if current_action is None:
            print(
                f"OBJ={obj}, curr_time={now_t}, time={obj.time/1000}, type={obj.type}",
            )
            if now_t >= obj.time / 1000:
                if isinstance(obj, HitCircle):
                    current_action = CircleAction(obj)

                elif isinstance(obj, Slider):
                    curr_uninherited_tp = get_active_uninherited_timing(timing_points, obj.time)
                    curr_inherited_tp = get_active_inherited_timing(timing_points, obj.time)

                    if curr_inherited_tp is None:
                        sv = 1.0
                    else:
                        sv = 100.0 / abs(curr_inherited_tp.beat_length)

                    current_action = SliderAction(obj, curr_uninherited_tp, sv, slider_multiplier)

                elif isinstance(obj, Spinner):
                    current_action = SpinnerAction(obj)
        
        if current_action is not None:
            current_action.update(now_t)
            if current_action.done:
                current_action = None
                osu_index += 1
        
        # ============= FPS Counter =============
        key = cv2.waitKey(1)
        if key == ord('f'):
            try:
                print("FPS:", 1 / (time.time() - loop_start))
            except ZeroDivisionError:
                pass

        # ============= Exit =============
        if key == ord('q'):
            cv2.destroyAllWindows()
            break

        time.sleep(0.0005)

if __name__ == "__main__":
    # pyautogui.PAUSE = 0.05
    main(save_image_mode=False, song_path="./test_songs/cin_normal.osu")
