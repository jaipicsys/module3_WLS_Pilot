class BoxCounter:
    """
    Counts closed boxes that leave the table.

    stable = number of boxes believed to be on the table.
    If fewer boxes are visible for leave_seconds, the missing ones are counted.
    """

    def __init__(self, appear_seconds=None, leave_seconds=3.0):
        # appear_seconds is kept only so existing calls still work
        self.leave = leave_seconds

        self.stable = 0          # boxes currently believed to be on the table
        self.total = 0           # boxes counted since start

        self._down_since = None
        self._down_max = 0

    def update(self, present, now):
        counted = 0

        # Box appeared (or same number): remember it, no count
        if present >= self.stable:
            self.stable = present
            self._down_since = None
            return 0

        # Fewer boxes than before: start / continue the timer
        if self._down_since is None:
            self._down_since = now
            self._down_max = present
        else:
            self._down_max = max(self._down_max, present)

        # Missing for leave_seconds -> count the boxes that went away
        if now - self._down_since >= self.leave:
            counted = self.stable - self._down_max
            self.stable = self._down_max
            self._down_since = None

        self.total += counted
        return counted