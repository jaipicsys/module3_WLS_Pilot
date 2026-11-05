#!/usr/bin/env python3
"""
export_osnet.py — download OSNet-x1.0 person-ReID weights (trained on MSMT17) and export to ONNX
for track_people.py (step 4 · Appearance).

Self-contained: the OSNet architecture is defined below (same layer names as Torchreid,
MIT licence), so no torchreid / boxmot install is needed — only torch, gdown, onnx(runtime).

  pip install gdown onnx onnxruntime-gpu      # or onnxruntime on CPU
  python3 tracking/export_osnet.py

Output: tracking/osnet_x1_0_msmt17.onnx  (input 1..N x 3 x 256 x 128 RGB, ImageNet-normalised;
        output N x 512 embedding). track_people.py picks it up automatically (REID_MODEL).

If Google Drive is blocked on the server, download the .pt manually from the URL printed below,
copy it to tracking/, and run with  --weights tracking/osnet_x1_0_msmt17.pt
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
from torch import nn

WEIGHTS_URL = "https://drive.google.com/uc?id=112EMUfBPYeYg70w-syK6V6Mx8-Qb9Q1M"  # osnet_x1_0_msmt17.pt
HERE = Path(__file__).resolve().parent


# --------------------------------------------------------------------------- #
# OSNet (Zhou et al., "Omni-Scale Feature Learning for Person Re-Identification", ICCV 2019)
# --------------------------------------------------------------------------- #
class ConvLayer(nn.Module):
    def __init__(self, in_c, out_c, k, stride=1, padding=0, groups=1):
        super().__init__()
        self.conv = nn.Conv2d(in_c, out_c, k, stride=stride, padding=padding, bias=False, groups=groups)
        self.bn = nn.BatchNorm2d(out_c)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        return self.relu(self.bn(self.conv(x)))


class Conv1x1(nn.Module):
    def __init__(self, in_c, out_c, stride=1, groups=1):
        super().__init__()
        self.conv = nn.Conv2d(in_c, out_c, 1, stride=stride, padding=0, bias=False, groups=groups)
        self.bn = nn.BatchNorm2d(out_c)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        return self.relu(self.bn(self.conv(x)))


class Conv1x1Linear(nn.Module):
    def __init__(self, in_c, out_c, stride=1):
        super().__init__()
        self.conv = nn.Conv2d(in_c, out_c, 1, stride=stride, padding=0, bias=False)
        self.bn = nn.BatchNorm2d(out_c)

    def forward(self, x):
        return self.bn(self.conv(x))


class LightConv3x3(nn.Module):
    """1x1 (linear) + depth-wise 3x3."""

    def __init__(self, in_c, out_c):
        super().__init__()
        self.conv1 = nn.Conv2d(in_c, out_c, 1, stride=1, padding=0, bias=False)
        self.conv2 = nn.Conv2d(out_c, out_c, 3, stride=1, padding=1, bias=False, groups=out_c)
        self.bn = nn.BatchNorm2d(out_c)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        return self.relu(self.bn(self.conv2(self.conv1(x))))


class ChannelGate(nn.Module):
    def __init__(self, in_c, reduction=16):
        super().__init__()
        self.global_avgpool = nn.AdaptiveAvgPool2d(1)
        self.fc1 = nn.Conv2d(in_c, in_c // reduction, 1, bias=True, padding=0)
        self.relu = nn.ReLU(inplace=True)
        self.fc2 = nn.Conv2d(in_c // reduction, in_c, 1, bias=True, padding=0)
        self.gate_activation = nn.Sigmoid()

    def forward(self, x):
        g = self.gate_activation(self.fc2(self.relu(self.fc1(self.global_avgpool(x)))))
        return x * g


class OSBlock(nn.Module):
    """Omni-scale block: 4 streams with 1-4 stacked light 3x3 convs, fused by a shared gate."""

    def __init__(self, in_c, out_c, bottleneck_reduction=4):
        super().__init__()
        mid = out_c // bottleneck_reduction
        self.conv1 = Conv1x1(in_c, mid)
        self.conv2a = LightConv3x3(mid, mid)
        self.conv2b = nn.Sequential(LightConv3x3(mid, mid), LightConv3x3(mid, mid))
        self.conv2c = nn.Sequential(*[LightConv3x3(mid, mid) for _ in range(3)])
        self.conv2d = nn.Sequential(*[LightConv3x3(mid, mid) for _ in range(4)])
        self.gate = ChannelGate(mid)
        self.conv3 = Conv1x1Linear(mid, out_c)
        self.downsample = Conv1x1Linear(in_c, out_c) if in_c != out_c else None

    def forward(self, x):
        identity = x
        x1 = self.conv1(x)
        x2 = (self.gate(self.conv2a(x1)) + self.gate(self.conv2b(x1))
              + self.gate(self.conv2c(x1)) + self.gate(self.conv2d(x1)))
        x3 = self.conv3(x2)
        if self.downsample is not None:
            identity = self.downsample(identity)
        return torch.relu(x3 + identity)


class OSNet(nn.Module):
    def __init__(self, num_classes=1000, layers=(2, 2, 2), channels=(64, 256, 384, 512), feature_dim=512):
        super().__init__()
        self.conv1 = ConvLayer(3, channels[0], 7, stride=2, padding=3)
        self.maxpool = nn.MaxPool2d(3, stride=2, padding=1)
        self.conv2 = self._make_layer(layers[0], channels[0], channels[1], reduce=True)
        self.conv3 = self._make_layer(layers[1], channels[1], channels[2], reduce=True)
        self.conv4 = self._make_layer(layers[2], channels[2], channels[3], reduce=False)
        self.conv5 = Conv1x1(channels[3], channels[3])
        self.global_avgpool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(nn.Linear(channels[3], feature_dim), nn.BatchNorm1d(feature_dim), nn.ReLU(inplace=True))
        self.classifier = nn.Linear(feature_dim, num_classes)

    @staticmethod
    def _make_layer(n, in_c, out_c, reduce):
        mods = [OSBlock(in_c, out_c)] + [OSBlock(out_c, out_c) for _ in range(n - 1)]
        if reduce:
            mods.append(nn.Sequential(Conv1x1(out_c, out_c), nn.AvgPool2d(2, stride=2)))
        return nn.Sequential(*mods)

    def forward(self, x):
        x = self.conv5(self.conv4(self.conv3(self.conv2(self.maxpool(self.conv1(x))))))
        v = self.fc(self.global_avgpool(x).flatten(1))
        return v if not self.training else self.classifier(v)  # eval -> 512-d embedding


def load_weights(model: nn.Module, path: Path):
    try:
        ckpt = torch.load(path, map_location="cpu", weights_only=False)
    except TypeError:  # torch < 1.13 has no weights_only argument
        ckpt = torch.load(path, map_location="cpu")
    sd = ckpt.get("state_dict", ckpt) if isinstance(ckpt, dict) else ckpt
    sd = {k.removeprefix("module."): v for k, v in sd.items()}
    own = model.state_dict()
    keep = {k: v for k, v in sd.items() if k in own and own[k].shape == v.shape}
    missing = [k for k in own if k not in keep and not k.startswith("classifier")]
    if missing:
        raise RuntimeError(f"{len(missing)} weights missing/mismatched, e.g. {missing[:5]}")
    model.load_state_dict(keep, strict=False)
    print(f"[osnet] loaded {len(keep)}/{len(own)} tensors from {path.name} (classifier skipped)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default=str(HERE / "osnet_x1_0_msmt17.pt"), help="downloaded here if missing")
    ap.add_argument("--out", default=str(HERE / "osnet_x1_0_msmt17.onnx"))
    ap.add_argument("--opset", type=int, default=12)
    a = ap.parse_args()

    wpath = Path(a.weights)
    if not wpath.exists():
        print(f"[osnet] downloading weights -> {wpath}\n         {WEIGHTS_URL}")
        import gdown
        if gdown.download(WEIGHTS_URL, str(wpath), quiet=False) is None or not wpath.exists():
            raise SystemExit("Download failed. Open the URL above in a browser, save the file as "
                             f"{wpath}, and re-run.")

    model = OSNet()
    load_weights(model, wpath)
    model.eval()

    dummy = torch.randn(2, 3, 256, 128)
    with torch.no_grad():
        ref = model(dummy).numpy()
    kw = dict(opset_version=a.opset, input_names=["images"], output_names=["embeddings"],
              dynamic_axes={"images": {0: "batch"}, "embeddings": {0: "batch"}}, do_constant_folding=True)
    try:
        torch.onnx.export(model, dummy, a.out, dynamo=False, **kw)  # torch >= 2.5: use the classic exporter
    except TypeError:
        torch.onnx.export(model, dummy, a.out, **kw)  # older torch
    print(f"[osnet] exported {a.out}")

    try:  # sanity check: ONNX output == PyTorch output
        import numpy as np
        import onnxruntime as ort
        sess = ort.InferenceSession(a.out, providers=["CPUExecutionProvider"])
        out = sess.run(None, {"images": dummy.numpy()})[0]
        print(f"[osnet] onnxruntime check: shape={out.shape} max|diff|={np.abs(out - ref).max():.2e}")
    except ImportError:
        print("[osnet] onnxruntime not installed — skipped check (pip install onnxruntime-gpu)")


if __name__ == "__main__":
    main()