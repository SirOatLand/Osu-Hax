import numpy as np
from windows_capture import WindowsCapture, Frame, InternalCaptureControl

class ScreenCapture:
    def __init__(self, window_name, monitor_index=1, cursor_capture=None, draw_border=None):
        self.latest_frame = None

        self.capture = WindowsCapture(
            cursor_capture=cursor_capture,
            draw_border=draw_border,
            monitor_index=monitor_index,
            window_name=window_name,
        )

        @self.capture.event
        def on_frame_arrived(frame: Frame, capture_control: InternalCaptureControl):
            self.latest_frame = frame.frame_buffer

        @self.capture.event 
        def on_closed():
            print("Capture Session Closed")

    def start(self):
        self.capture.start_free_threaded()

    def stop(self):
        self.capture.stop()
    
    def get_frame(self):
        return self.latest_frame
