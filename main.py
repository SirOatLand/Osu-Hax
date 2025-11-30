import time
import cv2
import numpy as np
import pyautogui
import math

from windows_capture import WindowsCapture, Frame, InternalCaptureControl
from inference import get_model

from imgdiff import detect_imgdiff
from save_image import save_image
from osu_input import *
from read_map import *
from config import SECOND_MONITOR
from replicate_songs import add_song_queue, queue_to_file
from coord_queue import CoordQueue, infer_to_queue

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

def main(save_image_mode, replicate, song_path):
    global start_time
    global osu_index
    global current_action
    global timing_points
    global slider_multiplier

    # Start thread for capturing screenshots
    capture.start_free_threaded()
    screenshot = None

    # Prepare HitObjects list
    osu_objects, timing_points, slider_multiplier, time_delay_300 = prep_osu_objects(song_path)
    osu_index = 0
    current_action = None

    # Initialize coord queue
    if replicate:
        model = get_model(
        model_id="osu-project-2-don-t-delete-ey2bp/2",
        api_key="n9ZqQYFxrPZCCverE0Lh"
        )
        object_queue = CoordQueue(threshold_t=1200)

    # Click start on osu screen
    osu_start_x, osu_start_y  = osu_to_screen(320, 170)
    pyautogui.moveTo(osu_start_x, osu_start_y)
    pyautogui.mouseDown()
    pyautogui.mouseUp()


    coord_queue = CoordQueue(threshold=25, cooldown_time=0.1)
    # osu changes process name on start
    wait_for_title_change(timeout=10)

    # Manually start the first object with shift + leftclick to sync the script
    while True:
        # if latest_frame is not None:  # Keeping inferring before the game starts
        #     screenshot = frame_to_numpy(latest_frame)
        #     infer_to_queue(model.infer(screenshot), coord_queue, screenshot, time.perf_counter()*1000)
        left_click = ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000
        shift_pressed = ctypes.windll.user32.GetAsyncKeyState(0x10) & 0x8000
        if left_click & shift_pressed:
            start_time = osu_objects[0].time/1000
            osu_index += 1
            break
        else:
            pass

    initial_timestamp = time.perf_counter()

    # Main Loop Starts
    while osu_index < len(osu_objects):
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
            # print(
            #     f"OBJ={obj}, curr_time={now_t:.5f}, time={(obj.time/1000):.5f}, index={osu_index}",
            # )
            pass
            if now_t >= (obj.time / 1000):
                if isinstance(obj, HitCircle):
                    click_x, click_y, q_class = coord_queue.pop("circle")
                    current_action = CircleAction(obj, click_x, click_y)

                elif isinstance(obj, Slider):
                    current_action = SliderAction(obj)

                elif isinstance(obj, Spinner):
                    current_action = SpinnerAction(obj)
        
        if current_action is not None:
            current_action.update(now_t)
            if current_action.done:
                current_action = None
                osu_index += 1


        # ============= Song Replication =============
        if replicate:
            add_song_queue(object_queue, model, screenshot, now_t)

        # ============= FPS Counter =============
        key = cv2.waitKey(1)
        if key == ord('f') or (ctypes.windll.user32.GetAsyncKeyState(0x46) & 0x0001):
            try:
                print("FPS:", 1 / (time.time() - loop_start))
            except ZeroDivisionError:
                pass

        # ============= Exit =============
        if key == ord('q') or (ctypes.windll.user32.GetAsyncKeyState(0x51) & 0x0001):
            cv2.destroyAllWindows()
            break
    if replicate:
        queue_to_file(object_queue)

if __name__ == "__main__":
    # pyautogui.PAUSE = 0.05
    song_name = "cin_normal.osu"
    main(save_image_mode=False, replicate=True, song_path="./test_songs/" + song_name)
