"""
OSNet appearance encoder: person crops -> 512-d embeddings.

  osnet_x1_0_msmt17.pt    -> run in PyTorch  (needs export_osnet.py in this folder: it holds the
                              OSNet network definition + load_weights)
  osnet_x1_0_msmt17.onnx  -> run with onnxruntime (no other file needed)

encoder(frame, boxes_xyxy) -> list of L2-normalised embeddings (None for boxes too small).
"""
import sys
from pathlib import Path

import cv2
import numpy as np

_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


def _crops(frame, boxes_xyxy, size_hw):
    H, W = frame.shape[:2]
    out, valid = [], []
    for x1, y1, x2, y2 in np.asarray(boxes_xyxy).astype(int):
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(W, x2), min(H, y2)
        if x2 - x1 < 4 or y2 - y1 < 8:
            valid.append(False)
            continue
        c = cv2.resize(frame[y1:y2, x1:x2], (size_hw[1], size_hw[0]))
        c = (c[:, :, ::-1].astype(np.float32) / 255.0 - _MEAN) / _STD   # BGR->RGB, ImageNet norm
        out.append(c.transpose(2, 0, 1))
        valid.append(True)
    return (np.stack(out) if out else None), valid


def _scatter(feats, valid):
    it = iter(feats)
    res = []
    for v in valid:
        if v:
            f = np.asarray(next(it), np.float32).ravel()
            res.append(f / (np.linalg.norm(f) + 1e-12))
        else:
            res.append(None)
    return res


class TorchOSNet:
    def __init__(self, weights, device):
        import torch
        here = Path(__file__).resolve().parent
        sys.path.insert(0, str(here))
        try:
            from export_osnet import OSNet, load_weights
        except ImportError as e:
            raise RuntimeError(
                f"Loading the OSNet .pt needs export_osnet.py in {here} (it defines the OSNet network). "
                "Or use the exported .onnx file instead."
            ) from e
        self.torch = torch
        use_cuda = str(device) != "cpu" and torch.cuda.is_available()
        self.dev = torch.device(str(device) if use_cuda else "cpu")
        m = OSNet()
        load_weights(m, Path(weights))
        self.m = m.eval().to(self.dev)
        self.hw = (256, 128)
        print(f"[reid] OSNet (PyTorch) {weights}  device={self.dev}")

    def __call__(self, frame, boxes_xyxy):
        batch, valid = _crops(frame, boxes_xyxy, self.hw)
        if batch is None:
            return [None] * len(valid)
        with self.torch.no_grad():
            feats = self.m(self.torch.from_numpy(batch).to(self.dev)).cpu().numpy()
        return _scatter(feats, valid)


class OnnxOSNet:
    def __init__(self, path, device):
        import onnxruntime as ort
        prov = (["CUDAExecutionProvider", "CPUExecutionProvider"]
                if str(device) != "cpu" else ["CPUExecutionProvider"])
        self.sess = ort.InferenceSession(
            path, providers=[p for p in prov if p in ort.get_available_providers()])
        inp = self.sess.get_inputs()[0]
        self.name = inp.name
        h, w = inp.shape[2], inp.shape[3]
        self.hw = (h if isinstance(h, int) else 256, w if isinstance(w, int) else 128)
        self.fixed_bs = inp.shape[0] if isinstance(inp.shape[0], int) else None
        print(f"[reid] OSNet (ONNX) {path}  providers={self.sess.get_providers()}")

    def __call__(self, frame, boxes_xyxy):
        batch, valid = _crops(frame, boxes_xyxy, self.hw)
        if batch is None:
            return [None] * len(valid)
        if self.fixed_bs:
            feats = []
            for s in range(0, len(batch), self.fixed_bs):
                ch = batch[s:s + self.fixed_bs]
                n = len(ch)
                if n < self.fixed_bs:
                    ch = np.concatenate([ch, np.repeat(ch[-1:], self.fixed_bs - n, 0)])
                feats.extend(self.sess.run(None, {self.name: ch})[0][:n])
        else:
            feats = self.sess.run(None, {self.name: batch})[0]
        return _scatter(feats, valid)


def build_encoder(path, device):
    return OnnxOSNet(path, device) if str(path).endswith(".onnx") else TorchOSNet(path, device)