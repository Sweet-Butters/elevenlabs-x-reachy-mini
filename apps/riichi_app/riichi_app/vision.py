"""CPU bounded person and approach detection, adapted from scripts/welcome_mode.py."""
from collections import deque
from pathlib import Path
import numpy as np

MODEL_PATH = Path.home() / ".cache" / "riichi" / "yolo11n.onnx"

class ApproachDetector:
    def __init__(self):
        self.history = deque()
        self.last_center = None

    def update(self, boxes, now, width, height):
        if not boxes:
            self.history.clear()
            self.last_center = None
            return False
        box = max(boxes, key=lambda b: (b[2]-b[0])*(b[3]-b[1]))
        center = ((box[0]+box[2])/2, (box[1]+box[3])/2)
        if self.last_center and ((center[0]-self.last_center[0])/width)**2 + ((center[1]-self.last_center[1])/height)**2 > 0.12**2:
            self.history.clear()
        self.last_center = center
        self.history.append((now, (box[2]-box[0])*(box[3]-box[1])))
        while self.history and now-self.history[0][0] > 1.5:
            self.history.popleft()
        if len(self.history) < 3 or now-self.history[0][0] < 0.8:
            return False
        growth = self.history[-1][1] / max(1, self.history[0][1]) - 1
        if growth >= 0.2:
            self.history.clear()
            return True
        return False

class PersonDetector:
    def __init__(self, cv2):
        import onnxruntime as ort
        if not MODEL_PATH.is_file():
            raise RuntimeError(f"YOLO 모델 없음: {MODEL_PATH}")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(MODEL_PATH), options, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.cv2 = cv2

    def detect(self, frame, confidence=0.35):
        cv2 = self.cv2
        height, width = frame.shape[:2]
        image = cv2.cvtColor(cv2.resize(frame, (640, 640)), cv2.COLOR_BGR2RGB)
        tensor = np.ascontiguousarray(image.transpose(2, 0, 1)[None], dtype=np.float32) / 255.0
        output = self.session.run(None, {self.input_name: tensor})[0][0].T
        people = output[output[:, 4] >= confidence]
        if not len(people):
            return []
        xywh = people[:, :4].copy()
        xywh[:, 0] -= xywh[:, 2]/2
        xywh[:, 1] -= xywh[:, 3]/2
        keep = cv2.dnn.NMSBoxes(xywh.tolist(), people[:, 4].tolist(), confidence, 0.45)
        result = []
        for i in np.array(keep).reshape(-1):
            x, y, w, h = xywh[i]
            result.append((max(0, int(x*width/640)), max(0, int(y*height/640)),
                           min(width, int((x+w)*width/640)), min(height, int((y+h)*height/640))))
        return result
