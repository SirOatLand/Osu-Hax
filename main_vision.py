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
from coord_queue import CoordQueue
from inference import get_model
import supervision as svi

latest_frame = None
current_action = None

MIN_CONFIDENCE = 0.85

capture = WindowsCapture(
    cursor_capture=None,
    draw_border=None,
    monitor_index=1,
    window_name="osu!",
)


def frame_to_numpy(frame: Frame):
    buf = frame.frame_buffer
    return cv2.cvtColor(buf, cv2.COLOR_BGRA2BGR)


def infer_to_queue(results, coord_queue, image_x, image_y):
    for pred in results.predictions:
        cls_name = pred.class_name  # or pred.class_name / pred.label depending on your YOLO version
        conf = pred.confidence  # usually between 0–1
        x = pred.x
        y = pred.y
        # print(conf)

        # 1. Filter by class
        if cls_name not in {"circle", "slider_head"}:
            continue

        # 2. Filter by confidence threshold
        if conf < MIN_CONFIDENCE:
            continue

        # 3. Convert coordinates
        x, y = ai_to_screen(x, y, image_x, image_y)

        # 4. Add to queue
        coord_queue.add(x, y, cls_name)

def infer_to_coords(results, image_x, image_y):
    coords = []

    for pred in results.predictions:
        cls_name = pred.class_name
        conf = pred.confidence
        x = pred.x
        y = pred.y

        # 1. Only keep desired classes
        if cls_name not in {"circle", "slider_head"}:
            continue

        # 2. Confidence filter
        if conf < MIN_CONFIDENCE:
            continue

        # 3. Convert coordinates to screen coords
        sx, sy = ai_to_screen(x, y, image_x, image_y)

        # 4. Append coord object
        coords.append((sx, sy, cls_name))

    return coords


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

    osu_start_x, osu_start_y = osu_to_screen(320, 170)
    pyautogui.moveTo(osu_start_x, osu_start_y)
    pyautogui.mouseDown()
    pyautogui.mouseUp()

    model = get_model(
        model_id="osu-project-2-9xzrs/2",
        api_key="n9ZqQYFxrPZCCverE0Lh"
    )
    coord_queue = CoordQueue(threshold=25, cooldown_time=0.1)
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

    # Persistent list of items that disappeared over multiple frames
    long_disappeared_list = []

    # Dictionary to count consecutive missing frames
    missing_counts = {}  # key = (x, y, cls)

    MISSING_THRESHOLD = 1  # number of consecutive frames before we flag

    while osu_index < len(osu_objects):

        # ========== FRAME PROCESSING ==========
        if latest_frame is not None:
            screenshot = frame_to_numpy(latest_frame)

            # Save persistent previous detections
            old_coords = list(coord_queue.queue)

            # Run inference for NEW detections only
            results = model.infer(screenshot)[0]
            new_coords = infer_to_coords(
                results, screenshot.shape[1], screenshot.shape[0]
            )
            infer_to_queue(results, coord_queue, screenshot.shape[1], screenshot.shape[0])
            results = []

        # ========== 1. DETECT DISAPPEARED COORDS ==========
        disappeared = find_disappeared_coords(old_coords, new_coords)
        print(old_coords, new_coords, disappeared)

        # Increment missing counts for disappeared items
        for c in disappeared:  # each c is a tuple (x, y, cls)
            key = c
            if key in missing_counts:
                missing_counts[key] += 1
            else:
                missing_counts[key] = 1

            # If missing enough frames → flag it
            if missing_counts[key] >= MISSING_THRESHOLD and key not in long_disappeared_list:
                long_disappeared_list.append(key)
                print(f"[LONG DISAPPEARED] Coordinate missing over {MISSING_THRESHOLD} frames: {key}")

        # Reset counts for coordinates that are still present
        for c in new_coords:  # still visible this frame
            key = c
            if key in missing_counts:
                missing_counts[key] = 0

        if disappeared:
            print("[INFO] Disappeared coords:", disappeared)

        # Process each disappeared coordinate
        for (dx, dy, dcls) in disappeared:

            # Remove from queue (non-class-based removal)
            coord_queue.remove(dx, dy, dcls)

            # ========== 2. MATCH TO NEXT OSU OBJECT ==========
            while osu_index < len(osu_objects):
                obj = osu_objects[osu_index]

                # Match based on expected class logic
                if isinstance(obj, HitCircle) and dcls == "circle":
                    action = CircleAction(obj, dx, dy)
                    break

                elif isinstance(obj, Slider) and dcls == "slider_head":
                    action = SliderAction(obj, dx, dy)
                    break

                elif isinstance(obj, Spinner) and dcls == "spinner":
                    action = SpinnerAction(obj)
                    break

                else:
                    # Not matching → advance to next osu object
                    print(f"[SKIP] {obj} does not match popped class {dcls}")
                    osu_index += 1

            # ========== 3. CREATE ACTION FOR MATCHED OBJECT ==========
            current_action = action

            # Increment to next osu object
            osu_index += 1

        # ========== 4. UPDATE ONGOING ACTION ==========
        if current_action is not None:
            now_t = time.perf_counter() + start_time - initial_timestamp
            current_action.update(now_t)
            if current_action.done:
                current_action = None

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
    main(save_image_mode=False, song_path="./test_songs/cin_normal.osu")
