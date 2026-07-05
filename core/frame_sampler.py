import numpy as np

class FrameSampler:

    def sample_9(self, start, end):
        return np.linspace(start, end, 9).tolist()

    def zoom_sample(self, center, range_sec=4, step=0.5):
        start = max(0, center - range_sec)
        end = center + range_sec
        return np.arange(start, end, step).tolist()