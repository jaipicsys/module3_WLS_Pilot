#!/usr/bin/env python3
"""
VERSION 2 — OSNET, NO NEW LEARNING: each person is learnt during their first 60 s of clean visibility, then locked.

track_people.py — person tracking with stable IDs through occlusion, pose change,
short detection loss, and exit/re-entry.

Two layers:

  1. Short-term (frames -> a few seconds)
     YOLO (your person model) + BoT-SORT with ReID, via Ultralytics `model.track`.
     Kalman motion + camera-motion compensation + appearance keep the same track id
     through brief occlusions / missed detections (lost tracks live `track_buffer` frames).

  2. Long-term (seconds -> minutes) — GlobalIDManager in this file
     Maps tracker ids -> stable "global" person IDs (P1, P2, ...).
     When the tracker gives up and spawns a NEW track id, we wait `confirm_frames`
     frames, average its appearance embedding, and try to re-link it to a lost person:
       * disappeared mid-frame (occluded / missed)  -> appearance + spatial prior
         (expected to reappear near the last seen location; radius grows with time)
       * disappeared at a frame edge (exited)        -> appearance only
     Each person keeps a gallery of diverse embeddings (different poses), updated
     only from clean, non-overlapping crops so occluders don't poison it.

Outputs (in --out-dir):
  <name>_tracked.mp4  annotated video (boxes, IDs, foot trails)
  <name>_tracks.txt   per-frame CSV rows for every box (pixel coords, debug fields)
  <name>_events.txt   human-readable log: new IDs, re-links, moves/swaps/unlabels, summary

Example:
  python tracking/track_people.py --source input/floor.mp4 --weights models/person.pt
  python tracking/track_people.py --source rtsp://user:pass@10.0.0.5/stream1 \
      --weights models/person.pt --reid-model yolo26s-reid.onnx --duration 600
"""

from __future__ import annotations

import argparse
import os

# RTSP over TCP: avoids the UDP packet loss behind 'error while decoding MB' / smeared frames
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

# =========================================================================== #
# INPUT CONFIG — edit here (command-line --source / --weights still override)
# =========================================================================== #
RTSP_SOURCE = "rtsp://192.168.2.22:8554/cam1"
VIDEO_SOURCE = "/home/yasmin/EigenState/Excavator/tracking/input/packing.mp4"
USE_RTSP = True  # True -> RTSP_SOURCE, False -> VIDEO_SOURCE
SOURCE = RTSP_SOURCE if USE_RTSP else VIDEO_SOURCE
WEIGHTS = "/home/yasmin/EigenState/Excavator/tracking/person.pt"
MAX_IDS = 7  # total people that can ever appear (closed set)
# Step 4 appearance model. First file that exists is used: the OSNet .pt weights run in PyTorch
# (no extra installs), or the .onnx made by export_osnet.py (needs onnxruntime). If neither exists
# -> torchvision ResNet50. Set REID_MODEL = None to force ResNet50.
REID_CANDIDATES = ["/home/yasmin/EigenState/Excavator/tracking/osnet_x1_0_msmt17.pt",
                   "/home/yasmin/EigenState/Excavator/tracking/osnet_x1_0_msmt17.onnx"]
REID_MODEL = next((p for p in REID_CANDIDATES if os.path.exists(p)), None)
GALLERY_MODE = "frozen"  # "rolling" = keep learning (verified samples only), "frozen" = learn first 60 s then lock
GALLERY_SIZE = 40
OUT_DIR = "tracking/output_osnet_frozen"
import queue
import signal
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment


# --------------------------------------------------------------------------- #
# Geometry helpers
# --------------------------------------------------------------------------- #
def iou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """IoU between two sets of xyxy boxes."""
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)), dtype=np.float32)
    x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2])
    y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / (area_a[:, None] + area_b[None, :] - inter + 1e-9)


def center(box) -> np.ndarray:
    return np.array([(box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0])


def foot(box) -> np.ndarray:
    """Bottom-centre of the box: best proxy for floor position."""
    return np.array([(box[0] + box[2]) / 2.0, box[3]])


def l2n(v: np.ndarray) -> np.ndarray:
    return v / (np.linalg.norm(v) + 1e-12)


# --------------------------------------------------------------------------- #
# Appearance encoders (self-contained; no dependency on Ultralytics' ReID class)
# --------------------------------------------------------------------------- #
_MEAN = np.array([0.485, 0.456, 0.406], np.float32)
_STD = np.array([0.229, 0.224, 0.225], np.float32)


def _crops(frame, boxes_xyxy, size_hw):
    H, W = frame.shape[:2]
    out, valid = [], []
    for x1, y1, x2, y2 in boxes_xyxy.astype(int):
        x1, y1, x2, y2 = max(0, x1), max(0, y1), min(W, x2), min(H, y2)
        if x2 - x1 < 4 or y2 - y1 < 8:
            valid.append(False)
            continue
        c = cv2.resize(frame[y1:y2, x1:x2], (size_hw[1], size_hw[0]))
        c = (c[:, :, ::-1].astype(np.float32) / 255.0 - _MEAN) / _STD  # BGR->RGB, ImageNet norm
        out.append(c.transpose(2, 0, 1))
        valid.append(True)
    return (np.stack(out) if out else None), valid


def _scatter(feats, valid):
    it = iter(feats)
    return [l2n(np.asarray(next(it), np.float32).ravel()) if v else None for v in valid]


class OnnxReID:
    """Any person-ReID ONNX (OSNet, yolo26-reid, ...): NCHW RGB ImageNet-normalised in, embedding out."""

    def __init__(self, path: str, device):
        import onnxruntime as ort
        prov = ["CUDAExecutionProvider", "CPUExecutionProvider"] if str(device) != "cpu" else ["CPUExecutionProvider"]
        self.sess = ort.InferenceSession(path, providers=[p for p in prov if p in ort.get_available_providers()])
        inp = self.sess.get_inputs()[0]
        self.name = inp.name
        h, w = inp.shape[2], inp.shape[3]
        self.hw = (h if isinstance(h, int) else 256, w if isinstance(w, int) else 128)
        self.fixed_bs = inp.shape[0] if isinstance(inp.shape[0], int) else None

    def __call__(self, frame, boxes_xyxy):
        batch, valid = _crops(frame, boxes_xyxy, self.hw)
        if batch is None:
            return [None] * len(valid)
        if self.fixed_bs:  # static-batch export: run one chunk at a time
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


class TorchvisionReID:
    """Generic fallback: ImageNet ResNet50 pooled features. Works anywhere, weaker than a real ReID model."""

    def __init__(self, device):
        import torch
        import torchvision
        self.torch = torch
        dev = "cpu" if str(device) == "cpu" or not torch.cuda.is_available() else (
            f"cuda:{device}" if str(device).isdigit() else "cuda")
        self.dev = torch.device(dev)
        try:
            m = torchvision.models.resnet50(weights="IMAGENET1K_V2")
        except TypeError:  # old torchvision
            m = torchvision.models.resnet50(pretrained=True)
        m.fc = torch.nn.Identity()
        self.m = m.eval().to(self.dev)
        self.hw = (256, 128)

    def __call__(self, frame, boxes_xyxy):
        batch, valid = _crops(frame, boxes_xyxy, self.hw)
        if batch is None:
            return [None] * len(valid)
        with self.torch.no_grad():
            feats = self.m(self.torch.from_numpy(batch).to(self.dev)).cpu().numpy()
        return _scatter(feats, valid)


class HistReID:
    """Last-resort, no-download fallback: HSV colour histograms of upper / lower body."""

    def __call__(self, frame, boxes_xyxy):
        H, W = frame.shape[:2]
        res = []
        for x1, y1, x2, y2 in boxes_xyxy.astype(int):
            x1, y1, x2, y2 = max(0, x1), max(0, y1), min(W, x2), min(H, y2)
            if x2 - x1 < 4 or y2 - y1 < 8:
                res.append(None)
                continue
            hsv = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
            mid = hsv.shape[0] // 2
            parts = [cv2.calcHist([p], [0, 1], None, [16, 8], [0, 180, 0, 256]).ravel() for p in (hsv[:mid], hsv[mid:])]
            res.append(l2n(np.sqrt(np.concatenate(parts))))
        return res


class TorchOSNetReID:
    """OSNet run directly in PyTorch from the downloaded .pt (no onnxruntime needed).
    The architecture comes from export_osnet.py, which must sit next to this script."""

    def __init__(self, weights: str, device):
        import sys
        import torch
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from export_osnet import OSNet, load_weights
        self.torch = torch
        dev = "cpu" if str(device) == "cpu" or not torch.cuda.is_available() else (
            f"cuda:{device}" if str(device).isdigit() else "cuda")
        self.dev = torch.device(dev)
        m = OSNet()
        load_weights(m, Path(weights))
        self.m = m.eval().to(self.dev)
        self.hw = (256, 128)

    def __call__(self, frame, boxes_xyxy):
        batch, valid = _crops(frame, boxes_xyxy, self.hw)
        if batch is None:
            return [None] * len(valid)
        with self.torch.no_grad():
            feats = self.m(self.torch.from_numpy(batch).to(self.dev)).cpu().numpy()
        return _scatter(feats, valid)


def Encoder(model: str | None, device):
    """x.onnx -> OnnxReID (needs onnxruntime); osnet*.pt -> OSNet in PyTorch; otherwise torchvision
    ResNet50; if that fails -> colour histograms."""
    if model and model.endswith(".onnx"):
        print(f"[reid] ONNX ReID model: {model}")
        return OnnxReID(model, device)
    if model and model.endswith(".pt"):
        print(f"[reid] OSNet (PyTorch) weights: {model}")
        return TorchOSNetReID(model, device)
    try:
        enc = TorchvisionReID(device)
        print("[reid] using torchvision ResNet50 (generic). For better IDs use an OSNet model")
        return enc
    except Exception as e:  # noqa: BLE001
        print(f"[reid] torchvision unavailable ({e}); falling back to colour histograms")
        return HistReID()


# --------------------------------------------------------------------------- #
# Long-term identity layer (closed set of max_ids people)
# --------------------------------------------------------------------------- #
@dataclass
class Person:
    gid: int
    first_frame: int
    last_frame: int
    last_box: np.ndarray
    exited: bool = False  # last seen touching a frame edge
    local_id: int | None = None  # current tracker id, None when lost ("free")
    gallery: list = field(default_factory=list)  # first learn_min samples are permanent anchors
    home: np.ndarray | None = None  # slow running average of foot position (usual station)
    frames_seen: int = 0
    path_px: float = 0.0
    relinks: int = 0
    reassigns: int = 0
    history: deque = field(default_factory=lambda: deque(maxlen=7))  # recent verification verdicts
    frozen: bool = False  # gallery + usual station locked after the learning window

    def appearance_dist(self, q: np.ndarray, topk: int = 3) -> float:
        """1 - mean of top-k cosine similarities against the gallery (robust to pose)."""
        if not self.gallery or q is None:
            return 1.0
        sims = np.asarray(self.gallery) @ q
        k = min(topk, len(sims))
        return float(1.0 - np.sort(sims)[-k:].mean())


@dataclass
class Pending:
    local_id: int
    first_frame: int
    first_box: np.ndarray
    embs: list = field(default_factory=list)
    confs: list = field(default_factory=list)
    frames: int = 0
    last_seen: int = 0
    was_gid: int | None = None  # set when this track lost its ID: it may only go back to an existing ID


class GlobalIDManager:
    """Maps tracker ids -> at most `max_ids` permanent person IDs.

    5a confirm   : new track must live `confirm_frames` with median conf >= confirm_min_conf
    5b/5c assign : an ID is given only if APPEARANCE ALONE passes (app_dist <= assign_app_max);
                   location / usual station only break ties. New P-ID only if far from everyone
                   (and < max_ids exist); otherwise the track stays "unknown" (grey "?")
    5d gallery   : diverse clean crops per person; in 'frozen' mode learnt only during the first
                   learn_s seconds a person is visible (never right after an overlap), then locked
    5e verify    : every verify_every frames EVERY linked track is compared with ALL people.
                   If it fails (own > keep_dist, or another ID clearly better) verify_votes times:
                   MOVE to that ID if free / SWAP if the holder fits us better / else UNLABEL
    """

    def __init__(self, fps: float, frame_w: int, frame_h: int, args, log):
        self.fps = fps
        self.W, self.H = frame_w, frame_h
        self.diag = float(np.hypot(frame_w, frame_h))
        self.a = args
        self.log = log
        self.people: dict[int, Person] = {}
        self.local2gid: dict[int, int] = {}
        self.pending: dict[int, Pending] = {}
        self.contacts: dict[frozenset, int] = {}  # {gidA,gidB} -> last frame they overlapped
        self.next_gid = 1

    # -- helpers ----------------------------------------------------------- #
    @property
    def full(self) -> bool:
        return len(self.people) >= self.a.max_ids

    def near_edge(self, box) -> bool:
        m = self.a.edge_margin
        return box[0] < m * self.W or box[1] < m * self.H or box[2] > (1 - m) * self.W or box[3] > (1 - m) * self.H

    def recently_in_contact(self, gid: int, frame_idx: int) -> bool:
        horizon = self.a.contact_memory_s * self.fps
        return any(gid in pair and frame_idx - f <= horizon for pair, f in self.contacts.items())

    def add_to_gallery(self, p: Person, emb: np.ndarray, frame_idx: int):
        if emb is None or p.frozen:
            return
        if self.recently_in_contact(p.gid, frame_idx):
            return  # never learn right after an overlap (possible swap)
        if len(p.gallery) >= self.a.learn_min and p.appearance_dist(emb) > self.a.gallery_accept_dist:
            return  # every learnt sample must itself verify against what we already know
        if p.gallery:
            sims = np.asarray(p.gallery) @ emb
            if sims.max() > self.a.gallery_dedup_sim:  # near-duplicate pose: skip, keep gallery diverse
                return
        p.gallery.append(emb)
        if len(p.gallery) > self.a.gallery_size:  # rolling mode: drop the most redundant non-anchor sample
            k = self.a.learn_min
            G = np.asarray(p.gallery[k:])
            S = G @ G.T
            np.fill_diagonal(S, -1)
            del p.gallery[k + int(S.max(axis=1).argmax())]
        self.maybe_freeze(p, frame_idx)

    def maybe_freeze(self, p: Person, frame_idx: int):
        """frozen mode: lock the gallery once the person was seen learn_s seconds (and has
        >= learn_min samples) or the gallery is full. After this nothing is ever added or dropped."""
        if p.frozen or self.a.gallery_mode != "frozen":
            return
        n = len(p.gallery)
        if n >= self.a.gallery_size or (p.frames_seen >= self.a.learn_s * self.fps and n >= self.a.learn_min):
            p.frozen = True
            self.log(frame_idx, f"GALLERY FROZEN P{p.gid}: {n} samples after {p.frames_seen / self.fps:.0f}s seen")

    def update_home(self, p: Person, box):
        if p.frozen:
            return
        f = foot(box)
        p.home = f.copy() if p.home is None else (1 - self.a.home_alpha) * p.home + self.a.home_alpha * f

    def bind(self, p: Person, lid: int, box, frame_idx):
        """Attach tracker id `lid` to person p (removing any other lid pointing at p)."""
        for old in [k for k, g in self.local2gid.items() if g == p.gid and k != lid]:
            del self.local2gid[old]
        self.local2gid[lid] = p.gid
        p.local_id, p.last_box, p.last_frame = lid, box.copy(), frame_idx
        p.exited = False
        p.history.clear()

    def new_person(self, pend: Pending, box, frame_idx) -> Person:
        p = Person(gid=self.next_gid, first_frame=pend.first_frame, last_frame=frame_idx, last_box=box.copy())
        p.gallery = []
        p.history = deque(maxlen=self.a.verify_window)
        for e in pend.embs:
            self.add_to_gallery(p, e, frame_idx)
        self.update_home(p, box)
        self.people[p.gid] = p
        self.next_gid += 1
        return p

    # -- main update ------------------------------------------------------- #
    def update(self, frame_idx: int, local_ids, boxes, confs, embed_fn):
        """Returns list of (local_id, gid or -1, state, app_dist) aligned with inputs."""
        n = len(local_ids)
        out = [None] * n
        ious = iou_matrix(boxes, boxes)
        np.fill_diagonal(ious, 0)
        clean = (ious.max(axis=1) if n > 1 else np.zeros(n)) < self.a.occlusion_iou
        verify_tick = frame_idx % self.a.verify_every == 0

        # Which boxes need an embedding this frame?
        need = []
        for i, lid in enumerate(local_ids):
            if lid in self.local2gid:
                if clean[i] and (verify_tick or frame_idx % self.a.gallery_every == 0):
                    need.append(i)
            elif clean[i] or lid not in self.pending or not self.pending[lid].embs:
                need.append(i)
        embs = {}
        if need:
            for i, e in zip(need, embed_fn(boxes[need])):
                embs[i] = e

        seen_lids = set(local_ids)
        ready = []  # pending tracks that are confirmed this frame
        linked_idx = {}  # gid -> row index this frame

        for i, lid in enumerate(local_ids):
            box = boxes[i]
            if lid in self.local2gid:  # ---- already linked (verified below in _verify)
                p = self.people[self.local2gid[lid]]
                p.path_px += float(np.linalg.norm(foot(box) - foot(p.last_box)))
                p.last_box, p.last_frame, p.local_id = box.copy(), frame_idx, lid
                p.frames_seen += 1
                self.maybe_freeze(p, frame_idx)
                self.update_home(p, box)
                linked_idx[p.gid] = i
                d = -1.0
                if embs.get(i) is not None:
                    d = p.appearance_dist(embs[i])
                    if d < self.a.gallery_accept_dist and all(v == "ok" for v in p.history):
                        self.add_to_gallery(p, embs[i], frame_idx)  # no-op once frozen
                out[i] = (lid, p.gid, "tracked", d)
            else:  # ---- new / pending / unknown track id
                pend = self.pending.get(lid)
                if pend is None:
                    pend = self.pending[lid] = Pending(lid, frame_idx, box.copy())
                pend.frames += 1
                pend.last_seen = frame_idx
                pend.confs.append(float(confs[i]))
                if embs.get(i) is not None and (clean[i] or not pend.embs):
                    pend.embs.append(embs[i])
                    if len(pend.embs) > 30:
                        pend.embs.pop(0)
                if (pend.frames >= self.a.confirm_frames and pend.embs
                        and np.median(pend.confs[-self.a.confirm_frames:]) >= self.a.confirm_min_conf):
                    ready.append(i)
                out[i] = (lid, -1, "pending", -1.0)

        # tracker ids that vanished -> person becomes FREE (re-link candidate)
        for lid, gid in self.local2gid.items():
            if lid not in seen_lids:
                p = self.people[gid]
                if p.local_id == lid and frame_idx - p.last_frame > self.a.lost_after_frames:
                    p.exited = self.near_edge(p.last_box)
                    p.local_id = None
                    p.history.clear()
        for lid in list(self.pending):
            if lid not in seen_lids and frame_idx - self.pending[lid].last_seen > self.a.confirm_frames:
                del self.pending[lid]  # track died before being confirmed -> false positive / flicker

        self._update_contacts(frame_idx, linked_idx, boxes)
        if verify_tick:
            self._verify(frame_idx, linked_idx, embs, local_ids, boxes, out)
        if ready:
            self._resolve(frame_idx, ready, local_ids, boxes, out)
        return out

    # -- 5b/5c: give an ID to a confirmed new/unknown track ----------------- #
    def _prior(self, p: Person, start_box, frame_idx):
        """Location + usual-station term. Only used to break ties between appearance matches."""
        gap_s = (frame_idx - p.last_frame) / self.fps
        if p.exited:
            sp = 0.0 if self.near_edge(start_box) else self.a.no_edge_penalty
        else:
            dist = np.linalg.norm(foot(start_box) - foot(p.last_box)) / self.diag
            radius = min(1.0, self.a.spatial_radius + self.a.walk_speed * gap_s)
            sp = self.a.spatial_weight * min(dist / radius, 1.0)
        hm = 0.0
        if p.home is not None:
            hm = self.a.home_weight * min(np.linalg.norm(foot(start_box) - p.home) / (self.a.home_radius * self.diag), 1.0)
        return sp + hm, gap_s

    def _resolve(self, frame_idx, ready, local_ids, boxes, out):
        """Give an ID to confirmed tracks. Rules:
        * appearance must pass on its own; location/station only break ties
        * the chosen free ID must also be the NEAREST of all known people (if an occupied person
          looks closer, it is ambiguous -> stay unknown until verification sorts it out)
        * a track that previously carried an ID can only go back to an existing ID, never NEW
        * NEW P-ID only for fresh tracks far from everyone, while < max_ids exist."""
        ready = [i for i in ready if local_ids[i] in self.pending]
        if not ready:
            return
        max_gap = self.a.max_lost_s * self.fps
        cands = [p for p in self.people.values()
                 if p.local_id is None and (self.full or frame_idx - p.last_frame <= max_gap)]
        costs = np.full((len(ready), len(cands)), 9.0, dtype=np.float32)
        details, queries, nearest_all = {}, {}, {}
        for r, i in enumerate(ready):
            pend = self.pending[local_ids[i]]
            q = queries[r] = l2n(np.mean(pend.embs, axis=0))
            all_d = {g: p.appearance_dist(q) for g, p in self.people.items() if p.gallery}
            nearest_all[r] = sorted(all_d.items(), key=lambda kv: kv[1])
            occupied_best = min((d for g, d in all_d.items() if self.people[g].local_id is not None), default=9.0)
            for c, p in enumerate(cands):
                app = all_d.get(p.gid, 1.0)
                limit = self.a.keep_dist if p.gid == pend.was_gid else self.a.assign_app_max
                if app > limit:  # appearance must pass ON ITS OWN
                    continue
                if p.gid != pend.was_gid and occupied_best < app - self.a.rank_margin:
                    continue  # someone already on screen looks more like this track -> ambiguous
                prior, gap_s = self._prior(p, pend.first_box, frame_idx)
                costs[r, c] = app + prior
                details[(r, c)] = (app, prior, gap_s)

        rows, cols = linear_sum_assignment(costs) if len(cands) else ([], [])
        matched = {r: c for r, c in zip(rows, cols) if costs[r, c] < 9}

        for r, i in enumerate(ready):
            lid = local_ids[i]
            pend = self.pending[lid]
            if r in matched:
                del self.pending[lid]
                p = cands[matched[r]]
                app, prior, gap_s = details[(r, matched[r])]
                p.relinks += 1
                for e in pend.embs:
                    self.add_to_gallery(p, e, frame_idx)
                how = "back" if p.gid == pend.was_gid else ("re-entry" if p.exited else "occlusion/miss")
                self.bind(p, lid, boxes[i], frame_idx)
                self.log(frame_idx, f"RELINK track {lid} -> P{p.gid} ({how}) gap={gap_s:.1f}s "
                                    f"app_dist={app:.2f} prior={prior:.2f}")
                out[i] = (lid, p.gid, "relinked", app)
                continue
            near = nearest_all[r]
            if (not self.full and pend.was_gid is None
                    and (not near or near[0][1] > self.a.new_id_min_dist)):
                del self.pending[lid]
                p = self.new_person(pend, boxes[i], frame_idx)
                self.bind(p, lid, boxes[i], frame_idx)
                txt = f" (nearest P{near[0][0]} dist={near[0][1]:.2f})" if near else ""
                self.log(frame_idx, f"NEW P{p.gid} from track {lid}{txt}"
                                    + (f"  [all {self.a.max_ids} IDs now created]" if self.full else ""))
                out[i] = (lid, p.gid, "new", -1.0)
            else:
                if pend.frames == self.a.confirm_frames or pend.frames % int(self.fps * 10) == 0:
                    if near:
                        g, dd = near[0]
                        holder = self.people[g].local_id
                        why = f"nearest P{g} dist={dd:.2f} ({f'held by track {holder}' if holder is not None else 'free'})"
                    else:
                        why = "no galleries"
                    was = f" (was P{pend.was_gid})" if pend.was_gid else ""
                    self.log(frame_idx, f"UNKNOWN track {lid}{was}: no ID passes the appearance test — {why}")
                out[i] = (lid, -1, "unknown", near[0][1] if near else -1.0)

    # -- contacts (used to block gallery learning right after overlaps) ----- #
    def _update_contacts(self, frame_idx, linked_idx, boxes):
        gids = list(linked_idx)
        for a_ in range(len(gids)):
            for b_ in range(a_ + 1, len(gids)):
                ga, gb = gids[a_], gids[b_]
                iou = iou_matrix(boxes[[linked_idx[ga]]], boxes[[linked_idx[gb]]])[0, 0]
                if iou > self.a.contact_iou:
                    self.contacts[frozenset((ga, gb))] = frame_idx
        horizon = self.a.contact_memory_s * self.fps
        for k in [k for k, f in self.contacts.items() if frame_idx - f > horizon]:
            del self.contacts[k]

    # -- 5e: verify EVERY linked track against ALL people -------------------- #
    def _unlabel(self, p: Person, lid, i, box, e, frame_idx, own, out, why):
        if self.local2gid.get(lid) == p.gid:
            del self.local2gid[lid]
        p.local_id = None
        p.history.clear()
        p.reassigns += 1
        pend = Pending(lid, frame_idx, box.copy(), embs=[e], confs=[1.0] * self.a.confirm_frames,
                       frames=self.a.confirm_frames, last_seen=frame_idx, was_gid=p.gid)
        self.pending[lid] = pend
        self.log(frame_idx, f"UNLABEL track {lid}: was P{p.gid} — {why}")
        out[i] = (lid, -1, "unknown", own)

    def _verify(self, frame_idx, linked_idx, embs, local_ids, boxes, out):
        """Every verify_every frames, compare each linked, clearly visible track with ALL people.
        Verdict per check:  'move:<g>' another ID is better by verify_margin and passes assign_app_max
                            'bad'      own distance above unlabel_dist
                            'ok'       otherwise
        Act only if the SAME non-ok verdict wins verify_votes of the last verify_window checks.
        People seen for less than verify_after_s are not verified yet: like the earlier version,
        their ID follows the tracker while their gallery is being learnt."""
        mature = {g: p for g, p in self.people.items() if len(p.gallery) >= self.a.learn_min}
        learn_frames = self.a.verify_after_s * self.fps
        dists, verdicts = {}, {}
        for gid, i in linked_idx.items():
            if gid in mature and embs.get(i) is not None:
                dists[gid] = {g: q.appearance_dist(embs[i]) for g, q in mature.items()}
        for gid, D in dists.items():
            p = self.people[gid]
            if p.frames_seen < learn_frames:
                continue
            own = D[gid]
            others = {g: d for g, d in D.items() if g != gid and self.people[g].frames_seen >= learn_frames}
            alt_g, alt_d = min(others.items(), key=lambda kv: kv[1]) if others else (None, 9.0)
            if alt_g is not None and alt_d <= self.a.assign_app_max and alt_d < own - self.a.verify_margin:
                v = f"move:{alt_g}"
            elif own > self.a.unlabel_dist:
                v = "bad"
            else:
                v = "ok"
            p.history.append(v)
            verdicts[gid] = (v, own, alt_g, alt_d)

        for gid, (v, own, alt_g, alt_d) in verdicts.items():
            if gid not in linked_idx or v == "ok":
                continue
            p = self.people[gid]
            if list(p.history).count(v) < self.a.verify_votes:
                continue
            i = linked_idx[gid]
            lid = local_ids[i]
            why = f"own dist={own:.2f}" + (f", looks like P{alt_g} ({alt_d:.2f})" if alt_g else "") + \
                  f", {list(p.history).count(v)}/{len(p.history)} checks"
            if v.startswith("move:"):
                q = self.people[alt_g]
                if q.local_id is None:  # target free -> move
                    p.local_id = None
                    p.history.clear()
                    q.history.clear()
                    p.reassigns += 1
                    q.reassigns += 1
                    self.bind(q, lid, boxes[i], frame_idx)
                    self.log(frame_idx, f"MOVE track {lid}: P{gid} -> P{alt_g} ({why})")
                    out[i] = (lid, alt_g, "reassigned", alt_d)
                    del linked_idx[gid]
                    linked_idx[alt_g] = i
                    continue
                j = linked_idx.get(alt_g)
                if j is not None and alt_g in dists:
                    D2 = dists[alt_g]
                    if D2[gid] < D2[alt_g]:  # the holder looks more like me -> swap
                        lid2 = local_ids[j]
                        self.local2gid[lid], self.local2gid[lid2] = alt_g, gid
                        p.local_id, q.local_id = lid2, lid
                        p.last_box, q.last_box = boxes[j].copy(), boxes[i].copy()
                        p.history.clear()
                        q.history.clear()
                        p.reassigns += 1
                        q.reassigns += 1
                        self.log(frame_idx, f"SWAP P{gid}<->P{alt_g} (tracks {lid},{lid2}): "
                                            f"straight={own + D2[alt_g]:.2f} crossed={alt_d + D2[gid]:.2f}")
                        out[i] = (lid, alt_g, "swapped", alt_d)
                        out[j] = (lid2, gid, "swapped", D2[gid])
                        linked_idx[gid], linked_idx[alt_g] = j, i
                        continue
                    # holder fits its own ID better: we look like an occupied person -> no safe target
                elif j is not None:
                    continue  # holder not clearly visible right now -> wait
            self._unlabel(p, lid, i, boxes[i], embs[i], frame_idx, own, out, why)
            del linked_idx[gid]

# --------------------------------------------------------------------------- #
# Video IO
# --------------------------------------------------------------------------- #
class RTSPReader:
    """Background reader that always hands out the latest frame (avoids RTSP buffer lag)."""

    def __init__(self, url: str):
        self.cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open stream {url}")
        self.q: queue.Queue = queue.Queue(maxsize=1)
        self.stopped = False
        self.t = threading.Thread(target=self._run, daemon=True)
        self.t.start()

    def _run(self):
        fails = 0
        while not self.stopped:
            ok, f = self.cap.read()
            if not ok:
                fails += 1
                if fails > 100:
                    self.stopped = True
                time.sleep(0.01)
                continue
            fails = 0
            if self.q.full():
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    pass
            self.q.put(f)

    def read(self):
        try:
            return True, self.q.get(timeout=5)
        except queue.Empty:
            return False, None

    def get(self, prop):
        return self.cap.get(prop)

    def release(self):
        self.stopped = True
        self.cap.release()


def color_for(gid: int):
    if gid < 0:
        return (160, 160, 160)
    rng = np.random.default_rng(gid * 7919)
    h = int(rng.integers(0, 180))
    hsv = np.uint8([[[h, 220, 255]]])
    return tuple(int(c) for c in cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)[0, 0])


def write_tracker_yaml(path: Path, args, fps: float):
    reid_model = "auto"  # BoT-SORT internal ReID (newer Ultralytics only); our step 4 uses --reid-model
    path.write_text(
        "tracker_type: botsort\n"
        f"track_high_thresh: {args.conf_high}\n"
        f"track_low_thresh: {args.conf}\n"
        f"new_track_thresh: {args.new_track_thresh}\n"
        f"track_buffer: {int(round(args.track_buffer_s * fps))}\n"
        "match_thresh: 0.8\n"
        "fuse_score: True\n"
        f"gmc_method: {args.gmc}\n"
        "proximity_thresh: 0.5\n"
        "appearance_thresh: 0.25\n"
        "with_reid: True\n"
        f"model: {reid_model}\n"
    )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default=SOURCE, help=".mp4 path or rtsp:// url (default: SOURCE in config block)")
    ap.add_argument("--weights", default=WEIGHTS, help="YOLO person model (default: WEIGHTS in config block)")
    ap.add_argument("--person-class", type=int, default=0)
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--device", default=None, help="e.g. 0, cpu")
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--conf", type=float, default=0.30, help="lowest det conf passed to tracker")
    ap.add_argument("--conf-high", type=float, default=0.50)
    ap.add_argument("--new-track-thresh", type=float, default=0.65)
    ap.add_argument("--track-buffer-s", type=float, default=3.0, help="tracker keeps lost tracks this long")
    ap.add_argument("--gmc", default="none", help="none for fixed CCTV; sparseOptFlow if camera moves")
    ap.add_argument("--reid-model", default=REID_MODEL if REID_MODEL and Path(REID_MODEL).exists() else None,
                    help="OSNet .pt (PyTorch) or person-ReID .onnx for step 4 (default: REID_MODEL in config block)")
    # long-term layer
    ap.add_argument("--max-ids", type=int, default=MAX_IDS, help="closed set: never more than this many people")
    ap.add_argument("--confirm-frames", type=int, default=10)
    ap.add_argument("--confirm-min-conf", type=float, default=0.6, help="median det conf needed to confirm a track")
    # appearance thresholds (1 - cosine sim to a person's gallery, top-3 mean). Calibrated on the
    # 152223 run: correct IDs median 0.13 / 99% < 0.30; wrong IDs 0.27-0.42. Recheck per model.
    ap.add_argument("--assign-app-max", type=float, default=0.28,
                    help="an ID is only given if appearance alone is below this (location only breaks ties)")
    ap.add_argument("--rank-margin", type=float, default=0.02,
                    help="skip a free ID if a person already on screen looks closer by more than this")
    ap.add_argument("--keep-dist", type=float, default=0.35,
                    help="a track that just lost its ID may go back to that same ID below this")
    ap.add_argument("--unlabel-dist", type=float, default=0.45,
                    help="remove a label only if own distance stays above this (big drift / different person)")
    ap.add_argument("--new-id-min-dist", type=float, default=0.30,
                    help="new P-ID only if the person is at least this far from ALL known people")
    ap.add_argument("--verify-every", type=int, default=3, help="frames between appearance checks of linked tracks")
    ap.add_argument("--verify-margin", type=float, default=0.08, help="another ID must be better by this much")
    ap.add_argument("--verify-window", type=int, default=7, help="recent checks considered")
    ap.add_argument("--verify-after-s", type=float, default=20,
                    help="start verifying a person after this many seconds seen (gallery learnt first)")
    ap.add_argument("--verify-votes", type=int, default=5, help="same verdict needed in the window before acting")
    ap.add_argument("--gallery-accept-dist", type=float, default=0.25, help="learn a sample only if this close")
    ap.add_argument("--gallery-size", type=int, default=GALLERY_SIZE)
    ap.add_argument("--gallery-every", type=int, default=5, help="frames between gallery updates")
    ap.add_argument("--gallery-dedup-sim", type=float, default=0.95)
    ap.add_argument("--gallery-mode", choices=["frozen", "rolling"], default=GALLERY_MODE,
                    help="frozen: learn only in the first --learn-s seconds of each person, then lock; "
                         "rolling: keep learning, drop oldest")
    ap.add_argument("--learn-s", type=float, default=60, help="seconds of visibility used to learn a person")
    ap.add_argument("--learn-min", type=int, default=10, help="keep learning until at least this many samples")
    ap.add_argument("--occlusion-iou", type=float, default=0.15, help="crops overlapping more are not 'clean'")
    ap.add_argument("--edge-margin", type=float, default=0.03)
    ap.add_argument("--max-lost-s", type=float, default=1800, help="forget a person after this long")
    ap.add_argument("--spatial-radius", type=float, default=0.08, help="fraction of diagonal")
    ap.add_argument("--walk-speed", type=float, default=0.10, help="diag fraction per second")
    ap.add_argument("--spatial-weight", type=float, default=0.15)
    ap.add_argument("--no-edge-penalty", type=float, default=0.08)
    ap.add_argument("--lost-after-frames", type=int, default=2)
    ap.add_argument("--home-weight", type=float, default=0.08, help="usual-station prior weight")
    ap.add_argument("--home-radius", type=float, default=0.15, help="diag fraction")
    ap.add_argument("--home-alpha", type=float, default=0.002, help="station average update rate")
    # 5e checks
    ap.add_argument("--contact-iou", type=float, default=0.2, help="IoU that counts as two people overlapping")
    ap.add_argument("--contact-memory-s", type=float, default=20, help="no gallery learning this long after overlap")
    # run control
    ap.add_argument("--trail", type=int, default=50, help="foot-trail length in frames (0 = off)")
    ap.add_argument("--duration", type=float, default=0, help="stop after N seconds (RTSP)")
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--show", action="store_true")
    return ap.parse_args()


def main():
    args = parse_args()
    if not args.reid_model or not args.reid_model.endswith((".pt", ".onnx")) or not Path(args.reid_model).exists():
        raise SystemExit("OSNet weights not found. Put osnet_x1_0_msmt17.pt here:\n  " + REID_CANDIDATES[0] + "\n"
                         "Download (browser): https://drive.google.com/uc?id=112EMUfBPYeYg70w-syK6V6Mx8-Qb9Q1M\n"
                         "Also keep export_osnet.py in the same folder (it holds the OSNet architecture).\n"
                         "(this version never falls back to ResNet)")
    from ultralytics import YOLO

    is_stream = args.source.lower().startswith(("rtsp://", "rtmp://", "http://", "https://"))
    cap = RTSPReader(args.source) if is_stream else cv2.VideoCapture(args.source)
    if not is_stream and not cap.isOpened():
        raise SystemExit(f"Cannot open {args.source}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    fps = fps if 1 <= fps <= 120 else 25.0
    ok, frame = cap.read()
    if not ok:
        raise SystemExit("No frames from source")
    H, W = frame.shape[:2]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = "rtsp_" + time.strftime("%Y%m%d_%H%M%S") if is_stream else Path(args.source).stem
    yaml_path = out_dir / f"{stem}_botsort.yaml"
    write_tracker_yaml(yaml_path, args, fps)

    model = YOLO(args.weights)
    encoder = Encoder(args.reid_model, args.device)

    writer = cv2.VideoWriter(str(out_dir / f"{stem}_tracked.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    tracks_f = open(out_dir / f"{stem}_tracks.txt", "w")
    tracks_f.write("frame,time_s,global_id,track_id,state,x1,y1,x2,y2,w,h,cx,cy,foot_x,foot_y,conf,app_dist\n")
    events_f = open(out_dir / f"{stem}_events.txt", "w")

    def log(fi, msg):
        line = f"[frame {fi:6d} | {fi / fps:8.2f}s] {msg}"
        events_f.write(line + "\n")
        events_f.flush()
        print(line)

    mgr = GlobalIDManager(fps, W, H, args, log)
    trails: dict[int, deque] = {}
    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("flag", True))

    fi, t0 = 0, time.time()
    log(0, f"source={args.source} {W}x{H}@{fps:.1f}fps tracker_yaml={yaml_path}")
    log(0, f"reid={args.reid_model or type(encoder).__name__} gallery={args.gallery_mode} "
           f"assign_app_max={args.assign_app_max} keep_dist={args.keep_dist} unlabel_dist={args.unlabel_dist} "
           f"verify={args.verify_votes}/{args.verify_window} learn_s={args.learn_s} verify_after_s={args.verify_after_s}")
    while ok and not stop["flag"]:
        res = model.track(frame, persist=True, tracker=str(yaml_path), classes=[args.person_class],
                          conf=args.conf, imgsz=args.imgsz, device=args.device, verbose=False)[0]
        b = res.boxes
        if b is not None and b.id is not None and len(b):
            boxes = b.xyxy.cpu().numpy().astype(np.float32)
            lids = b.id.cpu().numpy().astype(int).tolist()
            confs = b.conf.cpu().numpy()
        else:
            boxes, lids, confs = np.zeros((0, 4), np.float32), [], np.zeros(0)

        results = mgr.update(fi, lids, boxes, confs, lambda bx: encoder(frame, bx))

        vis = frame.copy()
        ts = fi / fps
        for (lid, gid, state, d), box, cf in zip(results, boxes, confs):
            x1, y1, x2, y2 = box
            fx, fy = foot(box)
            tracks_f.write(f"{fi},{ts:.3f},{gid},{lid},{state},{x1:.1f},{y1:.1f},{x2:.1f},{y2:.1f},"
                           f"{x2 - x1:.1f},{y2 - y1:.1f},{(x1 + x2) / 2:.1f},{(y1 + y2) / 2:.1f},"
                           f"{fx:.1f},{fy:.1f},{cf:.3f},{d:.3f}\n")
            col = color_for(gid)
            p1, p2 = (int(x1), int(y1)), (int(x2), int(y2))
            cv2.rectangle(vis, p1, p2, col, 2)
            label = f"P{gid}" if gid > 0 else f"? t{lid}"
            if state in ("relinked", "swapped", "reassigned"):
                label += " " + {"relinked": "RELINK", "swapped": "SWAP", "reassigned": "MOVE"}[state]
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(vis, (p1[0], p1[1] - th - 6), (p1[0] + tw + 4, p1[1]), col, -1)
            cv2.putText(vis, label, (p1[0] + 2, p1[1] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            if gid > 0 and args.trail:
                tr = trails.setdefault(gid, deque(maxlen=args.trail))
                tr.append((int(fx), int(fy)))
        if args.trail:
            for gid, tr in trails.items():
                if gid in mgr.people and mgr.people[gid].local_id is not None and len(tr) > 1:
                    cv2.polylines(vis, [np.array(tr, np.int32)], False, color_for(gid), 2)
        active = sum(1 for p in mgr.people.values() if p.local_id is not None)
        cv2.putText(vis, f"frame {fi}  t={ts:.1f}s  active={active}  total IDs={len(mgr.people)}",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        writer.write(vis)
        if args.show:
            cv2.imshow("tracking", vis)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        fi += 1
        if fi % 100 == 0:
            print(f"  {fi} frames, {fi / (time.time() - t0):.1f} fps")
        if (args.max_frames and fi >= args.max_frames) or (args.duration and ts >= args.duration):
            break
        ok, frame = cap.read()

    # summary
    log(fi, "=== SUMMARY ===")
    for p in sorted(mgr.people.values(), key=lambda p: p.gid):
        log(fi, f"P{p.gid}: first={p.first_frame / fps:.1f}s last={p.last_frame / fps:.1f}s "
                f"frames={p.frames_seen} relinks={p.relinks} swaps/moves={p.reassigns} path={p.path_px:.0f}px gallery={len(p.gallery)}"
                f"{' (frozen)' if p.frozen else ''}")
    cap.release()
    writer.release()
    tracks_f.close()
    events_f.close()
    if args.show:
        cv2.destroyAllWindows()
    print(f"Saved to {out_dir.resolve()}")


if __name__ == "__main__":
    main()