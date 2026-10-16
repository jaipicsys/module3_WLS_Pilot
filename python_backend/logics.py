class FrameLogic:
    """
    Per-camera processing logic.

    One instance is created per camera, so any state you need later
    (step tracking, timers, counters) can live on self.
    """

    def __init__(self, camera_id):
        self.camera_id = camera_id

    def process(self, frame):
        """
        Process a single frame.

        Returns the frame to display (annotated or not).
        Add detection / step / counting logic here later.
        """
        return frame