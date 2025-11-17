from time import time
import cv2 as cv
import numpy as np
from windows_capture import WindowsCapture, Frame, InternalCaptureControl

latest_frame = None

capture = WindowsCapture(
    cursor_capture=None,
    draw_border=None,
    monitor_index=1,
    window_name="osu!",
)

def frame_to_numpy(frame: Frame):
    buf = frame.frame_buffer
    return cv.cvtColor(buf, cv.COLOR_BGRA2BGR)

@capture.event
def on_frame_arrived(frame: Frame, capture_control: InternalCaptureControl):
    global latest_frame
    latest_frame = frame

@capture.event 
def on_closed():
    print("Capture Session Closed")
    cv.destroyAllWindows()

if __name__ == "__main__":
    capture.start_free_threaded()

    while True:
        loop_start = time()
        if latest_frame is not None:
            screenshot = frame_to_numpy(latest_frame)
            cv.imshow("Fake Osu", screenshot)
            
            try:
                fps = 1 / (time() - loop_start)
                print("FPS:", fps)
            except ZeroDivisionError:
                fps = 1 / (time() - loop_start + 0.001)
                print("FPS:", fps)

        key = cv.waitKey(1)
        if key == ord('q'):
            capture.stop()
            cv.destroyAllWindows()
            break
