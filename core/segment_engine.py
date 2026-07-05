class Segment:

    def __init__(self, name, start, end):
        self.name = name
        self.start = start
        self.end = end


class SegmentEngine:

    def build_segments(self, duration):

        step = duration / 5

        return [
            Segment("A", 0, step),
            Segment("B", step, step * 2),
            Segment("C", step * 2, step * 3),
            Segment("D", step * 3, step * 4),
            Segment("E", step * 4, duration),
        ]