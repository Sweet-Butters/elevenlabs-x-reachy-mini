"""CPU-only wrist motion detector using COCO pose keypoints."""
from collections import deque
import time

import numpy as np

from common import ROOT


class PoseDetector:
    def __init__(self, cv2):
        import onnxruntime as ort
        model = ROOT / "yolo11n-pose.onnx"
        if not model.is_file():
            raise RuntimeError("yolo11n-pose.onnx 없음: scripts/README.md 참조")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = opts.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model), opts, providers=["CPUExecutionProvider"])
        self.input = self.session.get_inputs()[0]
        self.cv2 = cv2
        self.height = int(self.input.shape[2])
        self.width = int(self.input.shape[3])

    def detect(self, frame):
        cv2 = self.cv2
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(cv2.resize(frame, (self.width, self.height)), cv2.COLOR_BGR2RGB)
        tensor = np.ascontiguousarray(rgb.transpose(2, 0, 1)[None], dtype=np.float32) / 255
        output = self.session.run(None, {self.input.name: tensor})[0][0].T
        rows = output[output[:, 4] >= 0.5]
        if len(rows) == 0:
            return []
        xywh = rows[:, :4].copy()
        xywh[:, 0:2] -= xywh[:, 2:4] / 2
        keep = cv2.dnn.NMSBoxes(xywh.tolist(), rows[:, 4].tolist(), 0.5, 0.45)
        poses = []
        for index in np.asarray(keep).reshape(-1):
            row = rows[index]
            box = (max(0, int(xywh[index, 0] * w / self.width)),
                   max(0, int(xywh[index, 1] * h / self.height)),
                   min(w, int((xywh[index, 0] + xywh[index, 2]) * w / self.width)),
                   min(h, int((xywh[index, 1] + xywh[index, 3]) * h / self.height)))
            if box[2] <= box[0] or box[3] <= box[1]:
                continue
            points = row[5:].reshape(17, 3).copy()
            points[:, 0] *= w / self.width
            points[:, 1] *= h / self.height
            poses.append((box, points))
        return poses


class WaveDetector:
    def __init__(self, cooldown=10):
        self.cooldown = cooldown
        self.history = {9: deque(), 10: deque()}
        self.last_box = None
        self.last_wave = -float("inf")

    def update(self, poses, now=None):
        now = time.monotonic() if now is None else now
        if not poses:
            self.history = {9: deque(), 10: deque()}
            self.last_box = None
            return None
        # Follow one person; a different person must build a new motion history.
        if self.last_box is None:
            box, points = max(poses, key=lambda p: (p[0][2]-p[0][0]) * (p[0][3]-p[0][1]))
        else:
            center = ((self.last_box[0]+self.last_box[2])/2, (self.last_box[1]+self.last_box[3])/2)
            box, points = min(poses, key=lambda p: ((p[0][0]+p[0][2])/2-center[0])**2 + ((p[0][1]+p[0][3])/2-center[1])**2)
            if abs((box[0]+box[2])-(self.last_box[0]+self.last_box[2])) > max(80, box[2]-box[0]):
                self.history = {9: deque(), 10: deque()}
        self.last_box = box
        width = max(1, box[2]-box[0])
        for wrist, elbow, shoulder in ((9, 7, 5), (10, 8, 6)):
            trail = self.history[wrist]
            if min(points[wrist, 2], points[elbow, 2], points[shoulder, 2]) >= 0.55 and points[wrist, 1] < min(points[elbow, 1], points[shoulder, 1] + 0.1*width):
                trail.append((now, float((points[wrist, 0] - points[shoulder, 0]) / width)))
            else:
                trail.clear()
            while trail and now - trail[0][0] > 1.5:
                trail.popleft()
            if now - self.last_wave < self.cooldown or len(trail) < 5 or now - trail[0][0] < 0.6:
                continue
            # Three clear horizontal legs, each at least 12% of body width.
            extremes = [trail[0]]
            direction = 0
            for sample in list(trail)[1:]:
                delta = sample[1] - extremes[-1][1]
                sign = 1 if delta > 0 else -1
                if direction == 0 and abs(delta) >= 0.12:
                    direction = sign
                    extremes.append(sample)
                elif direction and sign != direction and abs(delta) >= 0.12:
                    direction = sign
                    extremes.append(sample)
                elif direction == sign and abs(delta) > 0:
                    extremes[-1] = sample
            values = [v for _, v in trail]
            if max(values)-min(values) >= 0.2 and len(extremes) >= 4:
                self.last_wave = now
                trail.clear()
                return box
        return None
