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
    AR_delay = AR_delay - AR_DELAY_OFFSET

    osu_start_x, osu_start_y = osu_to_screen(320, 170)
    pyautogui.moveTo(osu_start_x, osu_start_y)
    pyautogui.mouseDown()
    pyautogui.mouseUp()

    model = get_model(
        model_id="osu-project-2-9xzrs/2",
        api_key="n9ZqQYFxrPZCCverE0Lh"
    )
    coord_queue = CoordQueue(threshold_dist=OBJ_THRESHOLD, cooldown_time=OBJ_COOLDOWN, min_detect_count=OBJ_MIN_COUNT, threshold_t=0)

    wait_for_title_change(timeout=10)
    while True:
        if latest_frame is not None:  # Keeping inferring before the game starts
            screenshot = frame_to_numpy(latest_frame)
            infer_to_queue(model.infer(screenshot), coord_queue, screenshot, time.perf_counter()*1000)
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
        # now_t = time.perf_counter() + start_time - initial_timestamp
        loop_start = time.time()
        # ========== FRAME PROCESSING ==========
        if latest_frame is not None:
            screenshot = frame_to_numpy(latest_frame)
            results = model.infer(screenshot)
            infer_to_queue(results, coord_queue, screenshot, time.perf_counter()*1000)
            results = None
        ready_to_process = []

        # Iterate through the queue without removing items
        for coord in coord_queue.queue:
            # print(now_t, time_detected, AR_delay, now - time_detected)
            if (time.perf_counter()*1000) - coord.time_ms >= AR_delay:
                ready_to_process.append(coord)

        if current_action is None and ready_to_process:
            coord = ready_to_process.pop(0)

            # ========== 2. MATCH TO NEXT OSU OBJECT ==========
            while osu_index < len(osu_objects) and current_action is None:
                obj = osu_objects[osu_index]
                print(f"Obtained object is {obj}")
                # Match based on expected class logic
                if isinstance(obj, HitCircle) and coord.cls == "circle":
                    x, y = ai_to_screen(coord.x, coord.y, coord.screen_x, coord.screen_y)
                    current_action = CircleAction(obj, x, y)
                    coord_queue.remove(coord)
                    break

                now_t = time.perf_counter() + start_time - initial_timestamp
                # print(f"now_t is {now_t}")
                if isinstance(obj, Slider):
                    print(f"Now is {now_t}, waiting for {obj.time/1000}.")
                    if now_t >= (obj.time / 1000):
#                         print("Condition passed")
                        current_action = SliderAction(obj)
                        coord_queue.remove(coord)
                        break
#                     print("Condition not passed")

                elif isinstance(obj, Spinner):
                    if now_t >= (obj.time / 1000):
                        current_action = SpinnerAction(obj)
                        coord_queue.remove(coord)
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
                        print(f"Skipping from {obj} to {coord.cls}. Step is {skip_steps}")
                        osu_index += skip_steps
                    else:
                        coord_queue.remove(coord)
                        break
            # print(f"End of class {dcls}")
        # print(f"Process length: {len(ready_to_process)}")
        # for item in ready_to_process:
        #     coord_queue.remove(*item)
        # ========== 3. CREATE ACTION FOR MATCHED OBJECT ==========
        # print(f"Current action is {current_action}")
        # ========== 4. UPDATE ONGOING ACTION ==========
        if current_action is not None:
            # print(f"Doing action {action}")
            now_t = time.perf_counter() + start_time - initial_timestamp
            current_action.update(now_t)
            if current_action.done:
                # print("Action done")
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
