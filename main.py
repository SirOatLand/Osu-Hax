import time
import cv2
import numpy as np
from windows_capture import WindowsCapture, Frame, InternalCaptureControl
from imgdiff import detect_imgdiff
from save_image import save_image

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


save_image_mode = True

if __name__ == "__main__":
    capture.start_free_threaded()
    screenshot = None
    tempscreenshot = None

    if save_image_mode:
        for i in range(5, 0, -1):
            print(i)
            time.sleep(1)
    while True:
        loop_start = time.time()
        if latest_frame is not None:
            if screenshot is not None:
                tempscreenshot = screenshot
            screenshot = frame_to_numpy(latest_frame)

            if save_image_mode:
                save_image(screenshot, folder_names=['img1', 'img2', 'img3', 'img4'], img_count=250, delay=0.2)
                cv2.imshow("screenshoting", screenshot)
            elif tempscreenshot is not None:
                cv2.imshow("Fake Osu", detect_imgdiff(tempscreenshot, screenshot, 30))

        try:
            print("FPS:", 1 / (time.time() - loop_start))
        except ZeroDivisionError:
            pass

        key = cv2.waitKey(1)
        if key == ord('q'):
            cv2.destroyAllWindows()
            break
