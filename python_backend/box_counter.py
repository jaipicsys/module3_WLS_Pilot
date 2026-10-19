class PickCounter:
    """
    Counts one unit each time the yellow person overlaps a closed box for
    overlap_frames frames in a row. Then it locks until the overlap has been
    gone for release_s seconds, so one box is counted once.
    """

    def __init__(self, overlap_frames=5, release_s=2.0, max_gap_frames=2):
        self.overlap_frames = overlap_frames
        self.release_s = release_s
        self.max_gap = max_gap_frames

        self.total = 0
        self.locked = False
        self.run = 0
        self._gap = 0
        self._last_overlap = None

    def reset(self):
        self.run = 0
        self._gap = 0

    def update(self, now, overlapping):
        """Call every frame. Returns 1 when a unit is counted, else 0."""
        if self.locked:
            if overlapping:
                self._last_overlap = now
            elif now - (self._last_overlap or now) >= self.release_s:
                self.locked = False
                self.run = 0
                self._gap = 0
            return 0

        if overlapping:
            self.run += 1
            self._gap = 0
        else:
            self._gap += 1
            if self._gap > self.max_gap:    # short detection dropouts are ignored
                self.run = 0

        if self.run >= self.overlap_frames:
            self.total += 1
            self.locked = True
            self._last_overlap = now
            self.run = 0
            return 1
        return 0