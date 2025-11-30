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
from coord_queue import CoordQueue, infer_to_queue
from inference import get_model
import supervision as svi
from collections import deque

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

    osu_objects, timing_points, slider_multiplier, time_delay_300, AR_delay = prep_osu_objects(song_path)
    osu_index = 0
    current_action = None
    AR_delay = AR_delay/1000 - AR_DELAY_OFFSET

    osu_start_x, osu_start_y = osu_to_screen(320, 170)
    pyautogui.moveTo(osu_start_x, osu_start_y)
    pyautogui.mouseDown()
    pyautogui.mouseUp()

    model = get_model(
        model_id="osu-project-2-9xzrs/2",
        api_key="n9ZqQYFxrPZCCverE0Lh"
    )
    coord_queue = CoordQueue(threshold=OBJ_THRESHOLD, cooldown_time=OBJ_COOLDOWN, min_detect_count=OBJ_MIN_COUNT)
    wait_for_title_change()
    wait_for_title_change(timeout=10)
    while True:
        if latest_frame is not None:  # Keeping inferring before the game starts
            screenshot = frame_to_numpy(latest_frame)
            infer_to_queue(model.infer(screenshot)[0], coord_queue, screenshot.shape[1], screenshot.shape[0])
        left_click = ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000
        shift_pressed = ctypes.windll.user32.GetAsyncKeyState(0x10) & 0x8000
        if left_click & shift_pressed:
            start_time = osu_objects[0].time / 1000
            osu_index += 1
            break
        else:
            pass

    initial_timestamp = time.perf_counter()



    while osu_index < len(osu_objects):
        loop_start = time.time()
        # ========== FRAME PROCESSING ==========
        if latest_frame is not None:
            screenshot = frame_to_numpy(latest_frame)
            results = model.infer(screenshot)[0]
            infer_to_queue(results, coord_queue, screenshot.shape[1], screenshot.shape[0])
            results = None

        now = time.perf_counter()
        ready_to_process = []

        # Iterate through the queue without removing items
        for item in coord_queue.queue:
            x, y, cls, time_detected = item
            # print(now, time_detected, AR_delay, now - time_detected)
            if now - time_detected >= AR_delay:
                ready_to_process.append(item)

        action = None
        for (dx, dy, dcls, ntime) in ready_to_process:
            # print(f"To process: {dx, dy, dcls, ntime}")
            # Remove from queue (non-class-based removal)
            # coord_queue.remove(dx, dy, dcls, ntime)

            # ========== 2. MATCH TO NEXT OSU OBJECT ==========
            while osu_index < len(osu_objects) and current_action is None:
                obj = osu_objects[osu_index]
                print(f"Obtained object is {obj}")
                # Match based on expected class logic
                if isinstance(obj, HitCircle) and dcls == "circle":
                    action = CircleAction(obj, dx, dy)
                    coord_queue.remove(dx, dy, dcls, ntime)
                    break

                now = time.perf_counter() + start_time - initial_timestamp
                print(f"Now is {now}")
                if isinstance(obj, Slider):
                    print(f"Now is {now}, waiting for {obj.time/1000}.")
                    if now >= (obj.time / 1000):
                        print("Condition passed")
                        action = SliderAction(obj)
                        coord_queue.remove(dx, dy, dcls, ntime)
                        break
                    print("Condition not passed")

                elif isinstance(obj, Spinner):
                    if now >= (obj.time / 1000):
                        action = SpinnerAction(obj)
                        coord_queue.remove(dx, dy, dcls, ntime)
                        break

                else:
                    obj_close = False
                    skip_steps = 0
                    for i in range(osu_index, osu_index+OSU_LOOKAHEAD):
                        if isinstance(osu_objects[i], Slider):
                            obj_close = True
                            skip_steps = i-osu_index
                            break
                    if obj_close:
                        print(f"Skipping from {obj} to {dcls}. Step is {skip_steps}")
                        osu_index += skip_steps
                    else:
                        coord_queue.remove(dx, dy, dcls, ntime)
                        break
            # print(f"End of class {dcls}")
        # print(f"Process length: {len(ready_to_process)}")
        # for item in ready_to_process:
        #     coord_queue.remove(*item)
        # ========== 3. CREATE ACTION FOR MATCHED OBJECT ==========
        current_action = action
        # print(f"Current action is {action}")


        # ========== 4. UPDATE ONGOING ACTION ==========
        if current_action is not None:
            # print(f"Doing action {action}")
            now_t = time.perf_counter() + start_time - initial_timestamp
            current_action.update(now_t)
            if current_action.done:
                print("Action done")
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
            cv2.destroyAllWindows()
            break


if __name__ == "__main__":
    # pyautogui.PAUSE = 0.05
    main(save_image_mode=False, song_path="./test_songs/cin_slider.osu")
