import time
import cv2
import pyautogui
from windows_capture import WindowsCapture, Frame, InternalCaptureControl
import supervision as svi
from inference import get_model
from dotenv import load_dotenv
import os

from osu_input import *
from read_map import *
from coord_queue import CoordQueue, infer_to_queue
from replicate_songs import queue_to_file


load_dotenv()

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


def main(replicate, replicated_path, song_path):
    global start_time
    global osu_index
    global current_action
    global timing_points
    global slider_multiplier

    capture.start_free_threaded()
    screenshot = None

    # Map Replication
    if replicate:
        removed_queue = None
        queue_record = []

    # Prepare variables
    osu_objects, timing_points, slider_multiplier, time_delay_300, AR_delay = prep_osu_objects(song_path)
    osu_index = 0
    current_action = None
    AR_delay = (AR_delay - AR_DELAY_OFFSET)


    # Loading Model
    model = get_model(
        model_id=os.getenv('MODEL_ID'),
        api_key=os.getenv('API_KEY'),
    )

    # Initializing objects queue
    coord_queue = CoordQueue(threshold_dist=OBJ_THRESHOLD, cooldown_time=OBJ_COOLDOWN, min_detect_count=OBJ_MIN_COUNT, threshold_t=0)

    # Click Start map on osu! screen
    osu_start_x, osu_start_y = osu_to_screen(320, 170)
    pyautogui.moveTo(osu_start_x, osu_start_y)
    pyautogui.mouseDown()
    pyautogui.mouseUp()

    # Check process name change which indicate map is loaded
    wait_for_title_change(timeout=10)

    first_time = time.perf_counter()
    while True:
        if latest_frame is not None:  # Keeping inferring before the game starts
            screenshot = frame_to_numpy(latest_frame)
            time_stamp = (time.perf_counter() - first_time) * 1000
            infer_to_queue(model.infer(screenshot), coord_queue, screenshot, time_stamp)
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
            results = model.infer(screenshot)
            time_stamp = (time.perf_counter() - initial_timestamp) * 1000
            infer_to_queue(results, coord_queue, screenshot, time_stamp)

            # load the results into the supervision Detections api
            detections = svi.Detections.from_inference(results[0])

            # create supervision annotators
            bounding_box_annotator = svi.BoxAnnotator()
            label_annotator = svi.LabelAnnotator()

            # annotate the image with our inference results
            annotated_image = bounding_box_annotator.annotate(scene=screenshot, detections=detections)
            annotated_image = label_annotator.annotate(scene=annotated_image, detections=detections)
            screenshot = annotated_image

            cv2.imshow("Fake Osu!", screenshot)

            results = None
        ready_to_process = []

        # Iterate through the queue without removing items
        for coord in coord_queue.queue:
            # print(now_t, time_detected, AR_delay, now - time_detected)
            time_stamp = (time.perf_counter() - initial_timestamp) * 1000
            if (time_stamp) - coord.time_ms >= AR_delay:
                ready_to_process.append(coord)

        if (current_action is None and ready_to_process)  or isinstance(osu_objects[osu_index], Spinner):
            if ready_to_process:
             coord = ready_to_process.pop(0)

            # ========== 2. MATCH TO NEXT OSU OBJECT ==========
            while (osu_index < len(osu_objects) and current_action is None):
                obj = osu_objects[osu_index]
                now_t = time.perf_counter() + start_time - initial_timestamp

                # Match based on expected class logic
                if isinstance(obj, HitCircle) and coord.cls == "circle":
                    x, y = ai_to_screen(coord.x, coord.y, coord.screen_x, coord.screen_y)
                    current_action = CircleAction(obj, x, y)
                    removed_queue = coord_queue.remove(coord)
                    break

                if isinstance(obj, Slider):
                    if now_t >= (obj.time / 1000):
                        current_action = SliderAction(obj)
                        removed_queue = coord_queue.remove(coord)
                        break

                elif isinstance(obj, Spinner):
                    if now_t >= (obj.time / 1000):
                        current_action = SpinnerAction(obj)
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

        # ========== 3. CREATE ACTION FOR MATCHED OBJECT ==========
        # print(f"Current action is {current_action}")
        # ========== 4. UPDATE ONGOING ACTION ==========
        if current_action is not None:
            # print(f"Doing action {action}")
            now_t = time.perf_counter() + start_time - initial_timestamp
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
            cv2.destroyAllWindows()
            break

        # ============= Song Replicate =============
        if replicate:
            if removed_queue is not None:
                queue_record.append(removed_queue)
                removed_queue = None

    if replicate:
        queue_to_file(queue_record, replicated_path)

if __name__ == "__main__":
    # pyautogui.PAUSE = 0.05
    song_name = "cin_normal.osu"
    main(replicate=True, replicated_path="./replicated_map/test1.osu", 
         song_path="./test_songs/" + song_name)
