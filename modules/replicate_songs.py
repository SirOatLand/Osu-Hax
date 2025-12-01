from inference import get_model
from osu_input import HitCircle, Slider, Spinner
from coord_queue import CoordQueue, DataAI

def make_osu_file(map_path, osu_objects, version="replicated"):

    title_field = "Title:" + map_path.split('/')[-1].split('.')[0] # get song name from path
    version_field = "Version:" + version

    osu_headers = ["osu file format v6", "[General]", "[Editor]", 
                   "[Metadata]", title_field, version_field,
                   "[Difficulty]", "[Events]", 
                   "[TimingPoints]", "0,0,0,0,0,0,0,0",
                   "[Colours]", "[HitObjects]"]

    with open(map_path, "w+") as f:
        for head in osu_headers:
            f.write(head + "\n")
        for obj in osu_objects:
            if isinstance(obj, HitCircle):
                values = [str(v) for v in vars(obj).values()]
                f.write(",".join(values))
                f.write("\n")

def create_osu_objects(ai_data):
    object = None
    x, y = ai_data.get_osu_coords()
    time = ai_data.time_ms
    # HitCircle
    if ai_data.cls == 'circle':
        object = HitCircle(x, y, time, 1, 0)

    return object

def add_song_queue(coord_queue: CoordQueue, model, screenshot, now_t):
    if screenshot is None:
        return
    results = model.infer(screenshot)
    clean = [
                {
                    "class": p.class_name,
                    "confidence": float(p.confidence),
                    "x": float(p.x),
                    "y": float(p.y),
                    "width": float(p.width),
                    "height": float(p.height),
                    "time_ms": round(now_t * 1000),
                    "screen_x": int(screenshot.shape[1]),
                    "screen_y": int(screenshot.shape[0])
                }
                for p in results[0].predictions
            ]
    for item in clean:
        data_ai = DataAI(item)
        coord_queue.add(data_ai)

def queue_to_file(coord_queue: CoordQueue | list, map_path="./replicated_map/test1"):
    print("Making .osu file......")
    osu_objects = []
    if isinstance(coord_queue, CoordQueue):
        for data_ai in coord_queue.queue:
            osu_objects.append(create_osu_objects(data_ai))
    else:
        for data_ai in coord_queue:
            osu_objects.append(create_osu_objects(data_ai))
    make_osu_file(map_path, osu_objects)
    print("Done!")

if __name__ == '__main__':
    import time
    import cv2
    from windows_capture import WindowsCapture, Frame, InternalCaptureControl
    import ctypes

    latest_frame = None

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

    capture.start_free_threaded()
    model = get_model(
        model_id="osu-project-2-don-t-delete-ey2bp/2",
        api_key="n9ZqQYFxrPZCCverE0Lh"
    )

    initial_timestamp = time.perf_counter()
    object_queue = CoordQueue(threshold_t=1200)
    while True:
        loop_start = time.time()
        if latest_frame is not None:
            screenshot = frame_to_numpy(latest_frame)

            now_t = time.perf_counter() - initial_timestamp

            add_song_queue(object_queue)
            
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

        
    queue_to_file(object_queue)