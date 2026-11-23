#!/usr/bin/env python3
"""
OSNET v2 — based on the OSNet-frozen version that worked best (run 20261111_140911).
Changes in v2 (everything else is identical):
  * every ID change is still decided by appearance (OSNet distance); thresholds are in the
    settings block and lowered: ASSIGN 0.22 (was 0.28), BACK 0.30 (was 0.35)
  * debug overlay in the video: per box the appearance distance to its own ID and to the next
    closest ID, detection confidence, a side table P1..P7, and the REASON for every ID change
  * P2->P4 fix: a track that has carried its ID since that person first appeared is only moved
    if its OWN appearance match is poor (> BACK) and another ID is better by >= 0.12; partly
    hidden boxes (< 80 % of the person's usual height) are not used for appearance checks
  * location tie-break: an ID lost long ago no longer gets an advantage over one lost just now

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
RTSP_SOURCE = "rtsp://192.168.2.10:8554/cam1"
VIDEO_SOURCE = "/home/yasmin/EigenState/Excavator/tracking/input/packing.mp4"
USE_RTSP = True  # True -> RTSP_SOURCE, False -> VIDEO_SOURCE
SOURCE = RTSP_SOURCE if USE_RTSP else VIDEO_SOURCE
WEIGHTS = "/home/pranav/pranav_mishra/module3_WLS_Pilot/python_backend/models/welspun_imvd_prsn_171126.pt"
MAX_IDS = 7  # total people that can ever appear (closed set)
# Step 4 appearance model. First file that exists is used: the OSNet .pt weights run in PyTorch
# (no extra installs), or the .onnx made by export_osnet.py (needs onnxruntime). If neither exists
# -> torchvision ResNet50. Set REID_MODEL = None to force ResNet50.
REID_CANDIDATES = ["/home/pranav/pranav_mishra/module3_WLS_Pilot/python_backend/models/osnet_x1_0_msmt17.pt",
                   "/home/pranav/pranav_mishra/module3_WLS_Pilot/python_backend/models/osnet_x1_0_msmt17.onnx"]
REID_MODEL = next((p for p in REID_CANDIDATES if os.path.exists(p)), None)
GALLERY_MODE = "frozen"  # "rolling" = keep learning (verified samples only), "frozen" = learn first 60 s then lock
GALLERY_SIZE = 40
# Appearance thresholds = OSNet distance (0 = identical look, higher = different), 1 - cosine
# similarity to the person's stored views (mean of the 3 best). Correct matches here: ~0.10-0.23.
ASSIGN_APP_MAX = 0.22  # give / re-link an ID only if the distance to it is <= this
KEEP_DIST = 0.30  # a track that just lost its ID may go back to that same ID if <= this
UNLABEL_DIST = 0.45  # remove a label only if the distance to its own ID stays above this
DEBUG_OVERLAY = True  # draw distances, confidences and switch reasons on the video
OUT_DIR = "tracking/output_osnet_frozen"
import queue
import re
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


# Inspection persons live in their OWN ID pool: gid 1001, 1002 ... shown as I1, I2 ...
# Operators / 'Person' class keep gid 1, 2, ... shown as P1, P2 ... The two pools never mix.
INSP_BASE = 1000


def pid_name(gid: int) -> str:
    return f"I{gid - INSP_BASE}" if gid >= INSP_BASE else f"P{gid}"


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
    bind_frame: int = 0  # when the current track got this ID
    bind_how: str = ""  # new / relink / move / swap
    heights: deque = field(default_factory=lambda: deque(maxlen=300))  # recent box heights
    last_check: tuple | None = None  # (frame, own dist, next closest gid, its dist) for the overlay
    last_d: tuple | None = None  # (frame, own dist) from the latest embedding of this person
    last_refresh: int = 0  # frame of the last periodic gallery refresh (or of the freeze)
    refreshes: int = 0  # how many refresh samples were learnt
    contact_frame: int = -10**9  # last frame this person overlapped another tracked person
    group: int = 0  # 0 = Person / operator IDs (P1..), 1 = inspection IDs (I1..): never shared
    own_hist: deque = field(default_factory=lambda: deque(maxlen=60))  # own-distance readings outside overlaps

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
    near: tuple | None = None  # (nearest gid, dist, holder track or None) for the overlay
    apart: dict = field(default_factory=dict)  # gid -> frames this track was on screen far from that person
    group: int = 0  # class group of this track (0 = Person, 1 = inspection)
    held: set = field(default_factory=set)  # IDs already reported as "held back" for this track


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
        self.next_insp = INSP_BASE + 1

    # -- helpers ----------------------------------------------------------- #
    def name(self, gid: int) -> str:
        return pid_name(gid)

    def cap(self, group: int) -> int:
        return self.a.max_ids if group == 0 else getattr(self.a, "max_insp_ids", 6)

    def full_for(self, group: int) -> bool:
        """Closed set per pool: P-IDs and I-IDs are counted separately."""
        return sum(1 for p in self.people.values() if p.group == group) >= self.cap(group)

    @property
    def full(self) -> bool:  # kept for the standalone script's summary line
        return self.full_for(0)

    def near_edge(self, box) -> bool:
        m = self.a.edge_margin
        return box[0] < m * self.W or box[1] < m * self.H or box[2] > (1 - m) * self.W or box[3] > (1 - m) * self.H

    def holder_fit(self, p: Person):
        """How well this person's own track USUALLY matches its ID: the median of its recent clean
        readings. One single reading is too noisy (a person who is partly hidden reads much worse for
        a moment), so it is only used when there are too few readings."""
        if len(p.own_hist) >= 5:
            return float(np.median(p.own_hist))
        return p.last_d[1] if p.last_d else None

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
            p.last_refresh = frame_idx
            self.log(frame_idx, f"GALLERY FROZEN {self.name(p.gid)}: {n} samples after {p.frames_seen / self.fps:.0f}s seen")

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
        p.bind_frame = frame_idx
        p.bind_how = ""

    def new_person(self, pend: Pending, box, frame_idx) -> Person:
        if pend.group == 0:
            gid, self.next_gid = self.next_gid, self.next_gid + 1
        else:
            gid, self.next_insp = self.next_insp, self.next_insp + 1
        p = Person(gid=gid, first_frame=pend.first_frame, last_frame=frame_idx, last_box=box.copy(),
                   group=pend.group)
        p.gallery = []
        p.history = deque(maxlen=self.a.verify_window)
        for e in pend.embs:
            self.add_to_gallery(p, e, frame_idx)
        self.update_home(p, box)
        self.people[p.gid] = p
        return p

    # -- main update ------------------------------------------------------- #
    def update(self, frame_idx: int, local_ids, boxes, confs, embed_fn, groups=None):
        """Returns list of (local_id, gid or -1, state, app_dist) aligned with inputs.
        groups: class group of every box (0 = Person, 1 = inspection); None = everybody is group 0.
        An ID is only ever given to a track of the SAME group."""
        n = len(local_ids)
        out = [None] * n
        grp = [int(g) for g in groups] if groups is not None else [0] * n

        # A linked track whose class group changed (BoT-SORT crossed an inspection person with an
        # operator, or the class vote flipped) cannot keep an ID of the other pool: release it.
        for i, lid in enumerate(local_ids):
            gid = self.local2gid.get(lid)
            if gid is not None and self.people[gid].group != grp[i]:
                p = self.people[gid]
                del self.local2gid[lid]
                if p.local_id == lid:
                    p.local_id = None
                p.history.clear()
                p.reassigns += 1
                self.log(frame_idx, f"UNLABEL track {lid}: was {self.name(gid)} - the track is now "
                                    f"{'an inspection person' if grp[i] else 'a Person'}")

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
                p.heights.append(float(box[3] - box[1]))
                self.maybe_freeze(p, frame_idx)
                self.update_home(p, box)
                linked_idx[p.gid] = i
                d = -1.0
                if embs.get(i) is not None:
                    d = p.appearance_dist(embs[i])
                    p.last_d = (frame_idx, d)
                    if not self.recently_in_contact(p.gid, frame_idx):
                        p.own_hist.append(d)  # the person's NORMAL fit, never measured right after an overlap
                    if d < self.a.gallery_accept_dist and all(v == "ok" for v in p.history):
                        self.add_to_gallery(p, embs[i], frame_idx)  # no-op once frozen
                out[i] = (lid, p.gid, "tracked", d)
            else:  # ---- new / pending / unknown track id
                pend = self.pending.get(lid)
                if pend is None:
                    pend = self.pending[lid] = Pending(lid, frame_idx, box.copy())
                pend.group = grp[i]
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

        if self.a.apart_frames > 0 and self.pending and linked_idx:
            for i, lid in enumerate(local_ids):
                pend = self.pending.get(lid)
                if pend is None or lid in self.local2gid:
                    continue
                for gid, j in linked_idx.items():
                    if (ious[i, j] < self.a.apart_iou
                            and np.linalg.norm(foot(boxes[i]) - foot(boxes[j])) / self.diag > self.a.apart_dist):
                        pend.apart[gid] = pend.apart.get(gid, 0) + 1

        self._update_contacts(frame_idx, linked_idx, boxes)
        if verify_tick:
            self._verify(frame_idx, linked_idx, embs, local_ids, boxes, out, confs)
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
            radius = min(self.a.max_radius, self.a.spatial_radius + self.a.walk_speed * gap_s)  # capped: long-lost IDs get no advantage
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
                 if p.local_id is None and (self.full_for(p.group) or frame_idx - p.last_frame <= max_gap)]
        costs = np.full((len(ready), len(cands)), 9.0, dtype=np.float32)
        details, queries, nearest_all = {}, {}, {}
        for r, i in enumerate(ready):
            pend = self.pending[local_ids[i]]
            q = queries[r] = l2n(np.mean(pend.embs, axis=0))
            all_d = {g: p.appearance_dist(q) for g, p in self.people.items()
                     if p.gallery and p.group == pend.group}   # compare only with the SAME pool
            nearest_all[r] = sorted(all_d.items(), key=lambda kv: kv[1])
            occupied_best = min((d for g, d in all_d.items() if self.people[g].local_id is not None), default=9.0)
            for c, p in enumerate(cands):
                if p.group != pend.group:
                    continue  # an inspection person never gets a P-ID (and vice versa)
                app = all_d.get(p.gid, 1.0)
                limit = self.a.keep_dist if p.gid == pend.was_gid else self.a.assign_app_max
                if app > limit:  # appearance must pass ON ITS OWN
                    continue
                # Co-visibility: this track was on screen, far from and not overlapping with, this
                # person's own track for >= apart_frames frames -> two different people. It may not
                # take the ID when the person is hidden for a moment (occlusion), whether she is
                # standing or walking. Not applied if the old holder USUALLY fitted this ID worse than
                # we do (then the holder was the wrong one) - judged by its median fit, never by one
                # noisy reading taken while it was being hidden.
                # (operator pool only for now: the inspector pool keeps its previous behaviour)
                hf = self.holder_fit(p) if p.group == 0 else (p.last_d[1] if p.last_d else None)
                if (self.a.apart_frames > 0 and p.gid != pend.was_gid
                        and pend.apart.get(p.gid, 0) >= self.a.apart_frames
                        and (hf is None or hf <= app + self.a.apart_fit_margin)):
                    continue
                # Long absence: after a long time away there is no time/location evidence left, so a BORDERLINE
                # match that is almost as close to somebody else is far more likely a look-alike than the
                # returning person. Such a track stays unlabelled until the match is clear (strong, or clearly
                # better than the second-best ID). Operator pool only for now.
                gap_now = (frame_idx - p.last_frame) / self.fps
                if (p.group == 0 and self.a.long_gap_s > 0 and p.gid != pend.was_gid
                        and gap_now >= self.a.long_gap_s and app > self.a.long_gap_strong):
                    second = min((d for g_, d in all_d.items() if g_ != p.gid), default=9.0)
                    if second - app < self.a.long_gap_margin:
                        if p.gid not in pend.held:
                            pend.held.add(p.gid)
                            self.log(frame_idx, f"HOLD track {local_ids[i]}: {self.name(p.gid)} was away {gap_now:.0f}s and "
                                                f"the match {app:.2f} is ambiguous (next best {second:.2f}) - not given")
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
                p.bind_how = "relink"
                self.log(frame_idx, f"RELINK track {lid} -> {self.name(p.gid)} ({how}) gap={gap_s:.1f}s "
                                    f"app_dist={app:.2f} prior={prior:.2f}")
                out[i] = (lid, p.gid, "relinked", app)
                continue
            near = nearest_all[r]
            if (not self.full_for(pend.group) and pend.was_gid is None
                    and (not near or near[0][1] > self.a.new_id_min_dist)):
                del self.pending[lid]
                p = self.new_person(pend, boxes[i], frame_idx)
                self.bind(p, lid, boxes[i], frame_idx)
                p.bind_how = "new"
                txt = f" (nearest {self.name(near[0][0])} dist={near[0][1]:.2f})" if near else ""
                self.log(frame_idx, f"NEW {self.name(p.gid)} from track {lid}{txt}"
                                    + (f"  [all {self.cap(pend.group)} {'I' if pend.group else 'P'}-IDs now created]"
                                       if self.full_for(pend.group) else ""))
                out[i] = (lid, p.gid, "new", -1.0)
            else:
                if near:
                    pend.near = (near[0][0], near[0][1], self.people[near[0][0]].local_id)
                if pend.frames == self.a.confirm_frames or pend.frames % int(self.fps * 10) == 0:
                    if near:
                        g, dd = near[0]
                        holder = self.people[g].local_id
                        why = f"nearest {self.name(g)} dist={dd:.2f} ({f'held by track {holder}' if holder is not None else 'free'})"
                    else:
                        why = "no galleries"
                    was = f" (was {self.name(pend.was_gid)})" if pend.was_gid else ""
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
                    self.people[ga].contact_frame = self.people[gb].contact_frame = frame_idx
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
                       frames=self.a.confirm_frames, last_seen=frame_idx, was_gid=p.gid, group=p.group)
        self.pending[lid] = pend
        self.log(frame_idx, f"UNLABEL track {lid}: was {self.name(p.gid)} — {why}")
        out[i] = (lid, -1, "unknown", own)

    def _refresh_galleries(self, frame_idx, linked_idx, dists, verdicts, embs, boxes, confs):
        """Periodic learning for frozen galleries (every refresh_every_s per person).
        A refresh sample is learnt ONLY when it cannot be a mislabel:
          * person verified 'ok' on every recent check, no overlap in the last contact_memory_s,
            and the ID is not newly bound / swapped / moved (refresh_settle_s)
          * full, clean, confident view (not cut by the frame edge, conf >= refresh_min_conf)
          * own distance <= refresh_accept_dist  AND  every other person is at least
            refresh_margin further away  -> the sample SEPARATES this person from the others
        The first learn_min anchors are never dropped; when the gallery is full the most
        redundant non-anchor sample is replaced, so the size stays constant."""
        a = self.a
        every = getattr(a, "refresh_every_s", 120.0)
        if every <= 0 or a.gallery_mode != "frozen":
            return
        for gid, (v, own, alt_g, alt_d) in verdicts.items():
            p = self.people[gid]
            i = linked_idx.get(gid)
            if v != "ok" or not p.frozen or i is None or gid not in dists:
                continue
            if frame_idx - p.last_refresh < every * self.fps:
                continue
            if frame_idx - p.bind_frame < a.refresh_settle_s * self.fps:
                continue
            if self.recently_in_contact(gid, frame_idx):
                continue
            if len(p.history) < 5 or any(h != "ok" for h in p.history):
                continue
            if confs is not None and float(confs[i]) < a.refresh_min_conf:
                continue
            if self.near_edge(boxes[i]) or embs.get(i) is None:
                continue
            if own > a.refresh_accept_dist or alt_g is None or alt_d < own + a.refresh_margin:
                continue
            emb = embs[i]
            if p.gallery and (np.asarray(p.gallery) @ emb).max() > a.gallery_dedup_sim:
                continue  # looks like something already stored: nothing new to learn
            p.gallery.append(emb)
            if len(p.gallery) > a.gallery_size:
                k = a.learn_min
                G = np.asarray(p.gallery[k:])
                S = G @ G.T
                np.fill_diagonal(S, -1)
                del p.gallery[k + int(S.max(axis=1).argmax())]
            p.last_refresh = frame_idx
            p.refreshes += 1
            self.log(frame_idx, f"GALLERY REFRESH {self.name(gid)}: +1 sample (own={own:.2f}, nearest "
                                f"{self.name(alt_g)}={alt_d:.2f}) gallery={len(p.gallery)} refreshes={p.refreshes}")

    def _contact_swap_check(self, frame_idx, linked_idx, embs, local_ids, boxes, out):
        """Two people overlapped and came apart with their tracker ids CROSSED (BoT-SORT gave
        each one the other's local id). Compare the pair jointly:
            straight = d(A, ID_A) + d(B, ID_B)      crossed = d(A, ID_B) + d(B, ID_A)
        If crossed is clearly smaller for `swap_votes` of the last 5 checks, swap the two IDs.
        Unlike the per-track check in _verify this does NOT skip a box for being 'partial'
        (a person walking away from the camera gets a smaller box and is still the same person),
        and it needs no single track to exceed keep_dist: the pair evidence is what counts."""
        a = self.a
        margin = getattr(a, "swap_margin", 0.15)
        votes_needed = getattr(a, "swap_votes", 3)
        learn_frames = a.verify_after_s * self.fps
        sv = self.__dict__.setdefault("_swap_votes", {})
        for pair, f in list(self.contacts.items()):
            if len(pair) != 2:
                continue
            ga, gb = tuple(pair)
            if ga not in linked_idx or gb not in linked_idx:
                continue
            pa, pb = self.people[ga], self.people[gb]
            if pa.group != pb.group:
                continue  # never swap an inspection person with an operator
            if len(pa.gallery) < a.learn_min or len(pb.gallery) < a.learn_min:
                continue
            if pa.frames_seen < learn_frames or pb.frames_seen < learn_frames:
                continue
            i, j = linked_idx[ga], linked_idx[gb]
            if embs.get(i) is None or embs.get(j) is None:   # embeddings exist only for clean boxes
                continue
            if self.near_edge(boxes[i]) or self.near_edge(boxes[j]):   # cut by the frame edge
                continue
            di = {g: self.people[g].appearance_dist(embs[i]) for g in (ga, gb)}
            dj = {g: self.people[g].appearance_dist(embs[j]) for g in (ga, gb)}
            straight, crossed = di[ga] + dj[gb], di[gb] + dj[ga]
            bad = (crossed + margin < straight and di[gb] <= a.keep_dist and dj[ga] <= a.keep_dist)
            # A real id swap makes BOTH tracks read much worse than they normally do. Two people who just
            # look alike do not (their own distance stays at its usual level) -> never swap those.
            deg = getattr(a, "swap_degrade", 0.10)
            if bad and deg > 0:
                ra = float(np.median(pa.own_hist)) if len(pa.own_hist) >= 10 else None
                rb = float(np.median(pb.own_hist)) if len(pb.own_hist) >= 10 else None
                bad = (ra is not None and rb is not None
                       and di[ga] - ra >= deg and dj[gb] - rb >= deg)
            hist = sv.setdefault(pair, deque(maxlen=5))
            hist.append(bad)
            strong = bad and (straight - crossed) >= getattr(a, "swap_strong_margin", 0.25)
            if not strong and sum(hist) < votes_needed:   # very clear evidence acts on the 1st clean check
                continue
            lid, lid2 = local_ids[i], local_ids[j]
            self.local2gid[lid], self.local2gid[lid2] = gb, ga
            pa.local_id, pb.local_id = lid2, lid
            pa.last_box, pb.last_box = boxes[j].copy(), boxes[i].copy()
            for q in (pa, pb):
                q.history.clear()
                q.reassigns += 1
                q.bind_frame = frame_idx
                q.bind_how = "swap"
            self.log(frame_idx, f"SWAP {self.name(ga)}<->{self.name(gb)} (tracks {lid},{lid2}) after overlap: "
                                f"straight={straight:.2f} crossed={crossed:.2f}")
            out[i] = (lid, gb, "swapped", di[gb])
            out[j] = (lid2, ga, "swapped", dj[ga])
            linked_idx[ga], linked_idx[gb] = j, i
            hist.clear()

    def _verify(self, frame_idx, linked_idx, embs, local_ids, boxes, out, confs=None):
        """Every verify_every frames, compare each linked, clearly visible track with ALL people.
        Verdict per check:  'move:<g>' another ID is better by verify_margin and passes assign_app_max
                            'bad'      own distance above unlabel_dist
                            'ok'       otherwise
        Act only if the SAME non-ok verdict wins verify_votes of the last verify_window checks.
        People seen for less than verify_after_s are not verified yet: like the earlier version,
        their ID follows the tracker while their gallery is being learnt."""
        self._contact_swap_check(frame_idx, linked_idx, embs, local_ids, boxes, out)
        mature = {g: p for g, p in self.people.items() if len(p.gallery) >= self.a.learn_min}
        learn_frames = self.a.verify_after_s * self.fps
        dists, verdicts = {}, {}
        for gid, i in linked_idx.items():
            h = boxes[i][3] - boxes[i][1]
            ph = self.people[gid].heights
            partial = len(ph) >= 30 and h < self.a.partial_h_ratio * float(np.median(ph))
            if gid in mature and embs.get(i) is not None and not partial:  # full, clean views only
                dists[gid] = {g: q.appearance_dist(embs[i]) for g, q in mature.items()
                              if q.group == self.people[gid].group}
        for gid, D in dists.items():
            p = self.people[gid]
            if p.frames_seen < learn_frames:
                continue
            own = D[gid]
            others = {g: d for g, d in D.items() if g != gid and self.people[g].frames_seen >= learn_frames}
            alt_g, alt_d = min(others.items(), key=lambda kv: kv[1]) if others else (None, 9.0)
            p.last_check = (frame_idx, own, alt_g, alt_d)
            # the track that has carried this ID since the person first appeared needs much stronger
            # evidence: its OWN match must really be poor, not just a bit worse than another ID's
            stable = p.bind_how == "new" and frame_idx - p.bind_frame >= self.a.stable_s * self.fps
            # ... and so does ANY binding (also a re-link) that has carried this ID, on the same track
            # and without overlapping anybody, for stable_s: a continuous, undisturbed track keeps its
            # ID unless its own match is really poor (> keep_dist). A noisy 0.22-vs-0.13 reading must
            # not hand an absent person's ID to somebody who already has one.
            calm = frame_idx - max(p.bind_frame, p.contact_frame) >= self.a.stable_s * self.fps
            stable = stable or calm
            margin = self.a.stable_margin if stable else self.a.verify_margin
            if (alt_g is not None and alt_d <= self.a.assign_app_max and alt_d < own - margin
                    and (not stable or own > self.a.keep_dist)):
                v = f"move:{alt_g}"
            elif own > self.a.unlabel_dist:
                v = "bad"
            else:
                v = "ok"
            p.history.append(v)
            verdicts[gid] = (v, own, alt_g, alt_d)

        self._refresh_galleries(frame_idx, linked_idx, dists, verdicts, embs, boxes, confs)

        for gid, (v, own, alt_g, alt_d) in verdicts.items():
            if gid not in linked_idx or v == "ok":
                continue
            p = self.people[gid]
            if list(p.history).count(v) < self.a.verify_votes:
                continue
            i = linked_idx[gid]
            lid = local_ids[i]
            why = f"own dist={own:.2f}" + (f", looks like {self.name(alt_g)} ({alt_d:.2f})" if alt_g else "") + \
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
                    q.bind_how = "move"
                    self.log(frame_idx, f"MOVE track {lid}: {self.name(gid)} -> {self.name(alt_g)} ({why})")
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
                        p.bind_frame = q.bind_frame = frame_idx
                        p.bind_how = q.bind_how = "swap"
                        self.log(frame_idx, f"SWAP {self.name(gid)}<->{self.name(alt_g)} (tracks {lid},{lid2}): "
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
        self.received = 0  # frames the stream delivered
        self.dropped = 0   # frames thrown away because the tracker was still busy with the previous one
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
            self.received += 1
            if self.q.full():
                try:
                    self.q.get_nowait()
                    self.dropped += 1
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
# Debug overlay
# --------------------------------------------------------------------------- #
EVENT_SHOW_FRAMES = 45  # how long a switch reason stays under the box (3 s at 15 fps)
_FONT = cv2.FONT_HERSHEY_SIMPLEX


def _text(img, txt, org, scale=0.5, color=(255, 255, 255), thick=1, bg=(0, 0, 0)):
    (tw, th), base = cv2.getTextSize(txt, _FONT, scale, thick)
    x, y = int(org[0]), int(org[1])
    cv2.rectangle(img, (x - 2, y - th - 3), (x + tw + 2, y + base), bg, -1)
    cv2.putText(img, txt, (x, y), _FONT, scale, color, thick, cv2.LINE_AA)
    return th + base + 4


def _fmt_d(d):
    return f"{d:.2f}" if d is not None and d >= 0 else "--"


def draw_debug(vis, fi, results, boxes, confs, mgr, args, track_events, recent_events):
    """Per box: ID, appearance distance to its own ID and to the next closest ID, detection conf,
    and the reason of any ID change in the last 3 s. Side table P1..P7. Recent events panel."""
    H, W = vis.shape[:2]
    stale = int(2 * mgr.fps)
    for (lid, gid, state, d), box, cf in zip(results, boxes, confs):
        x1, y1, x2, y2 = [int(v) for v in box]
        lines = []
        if gid > 0:
            p = mgr.people[gid]
            lc = p.last_check if p.last_check and fi - p.last_check[0] <= stale else None
            ld = p.last_d if p.last_d and fi - p.last_d[0] <= stale else None
            own = lc[1] if lc else (ld[1] if ld else None)
            ok = own is not None and own <= args.assign_app_max
            lines.append((f"d({mgr.name(gid)})={_fmt_d(own)}  conf={cf:.2f}", (0, 255, 0) if ok else (0, 200, 255)))
            if lc and lc[2] is not None:
                lines.append((f"next {mgr.name(lc[2])}={_fmt_d(lc[3])}", (200, 200, 200)))
        else:
            pend = mgr.pending.get(lid)
            if pend is not None and pend.near:
                g, dd, holder = pend.near
                who = f"held t{holder}" if holder is not None else "free"
                lines.append((f"? nearest {mgr.name(g)}={_fmt_d(dd)} ({who}) conf={cf:.2f}", (0, 200, 255)))
                lines.append((f"needs <= {args.assign_app_max:.2f} to get an ID", (180, 180, 180)))
            else:
                lines.append((f"? waiting ({state}) conf={cf:.2f}", (180, 180, 180)))
        ev = track_events.get(lid)
        if ev and fi - ev[0] <= EVENT_SHOW_FRAMES:
            msg = ev[1]
            lines.append((msg[:58], (0, 255, 255)))
            if len(msg) > 58:
                lines.append((msg[58:116], (0, 255, 255)))
        y = min(y2 + 16, H - 6 * 16)
        for txt, colr in lines:
            y += _text(vis, txt, (x1, y), 0.45, colr)

    # side table: one row per person
    hdr = f"ID  track  d(own)  next   | assign<={args.assign_app_max:.2f} unlabel>{args.unlabel_dist:.2f}"
    x0, y = W - cv2.getTextSize(hdr, _FONT, 0.45, 1)[0][0] - 12, 60
    y += _text(vis, hdr, (x0, y), 0.45, (255, 255, 255))
    for g in sorted(mgr.people):
        p = mgr.people[g]
        lc = p.last_check if p.last_check and fi - p.last_check[0] <= stale else None
        ld = p.last_d if p.last_d and fi - p.last_d[0] <= stale else None
        own = lc[1] if lc else (ld[1] if ld else None)
        trk = f"t{p.local_id}" if p.local_id is not None else "lost"
        nxt = f"{mgr.name(lc[2])}={_fmt_d(lc[3])}" if lc and lc[2] is not None else ""
        y += _text(vis, f"{mgr.name(g):<3} {trk:>6}  {_fmt_d(own):>5}  {nxt}", (x0, y), 0.45, color_for(g))
    # recent events panel
    y = H - 10 - 18 * len(recent_events)
    for f, msg in recent_events:
        y += _text(vis, f"[{f}] {msg[:120]}", (10, y), 0.45, (0, 255, 255))


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
    ap.add_argument("--max-insp-ids", type=int, default=6,
                    help="closed set of INSPECTION persons (own pool: I1, I2 ...), separate from --max-ids")
    ap.add_argument("--confirm-frames", type=int, default=10)
    ap.add_argument("--confirm-min-conf", type=float, default=0.6, help="median det conf needed to confirm a track")
    # appearance thresholds (1 - cosine sim to a person's gallery, top-3 mean). Calibrated on the
    # 152223 run: correct IDs median 0.13 / 99% < 0.30; wrong IDs 0.27-0.42. Recheck per model.
    ap.add_argument("--assign-app-max", type=float, default=ASSIGN_APP_MAX,
                    help="an ID is only given if appearance alone is below this (location only breaks ties)")
    ap.add_argument("--rank-margin", type=float, default=0.02,
                    help="skip a free ID if a person already on screen looks closer by more than this")
    ap.add_argument("--keep-dist", type=float, default=KEEP_DIST,
                    help="a track that just lost its ID may go back to that same ID below this")
    ap.add_argument("--unlabel-dist", type=float, default=UNLABEL_DIST,
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
    ap.add_argument("--max-radius", type=float, default=0.25, help="cap of the search radius (diag fraction)")
    ap.add_argument("--stable-s", type=float, default=60,
                    help="a track holding the ID it got when the person first appeared for this long is 'stable' ...")
    ap.add_argument("--stable-margin", type=float, default=0.12,
                    help="... and is only moved if its own distance > keep_dist AND another ID is better by this")
    ap.add_argument("--partial-h-ratio", type=float, default=0.8,
                    help="no appearance check when the box is shorter than this x the person's usual height")
    ap.add_argument("--no-edge-penalty", type=float, default=0.08)
    ap.add_argument("--lost-after-frames", type=int, default=2)
    ap.add_argument("--home-weight", type=float, default=0.08, help="usual-station prior weight")
    ap.add_argument("--home-radius", type=float, default=0.15, help="diag fraction")
    ap.add_argument("--home-alpha", type=float, default=0.002, help="station average update rate")
    # 5e checks
    ap.add_argument("--swap-margin", type=float, default=0.15,
                    help="after an overlap, swap two IDs if crossed distances are smaller by this much")
    ap.add_argument("--swap-votes", type=int, default=3,
                    help="... in this many of the last 5 checks")
    ap.add_argument("--swap-degrade", type=float, default=0.10,
                    help="pair swap only if BOTH tracks read at least this much worse than their own usual "
                         "distance (0 = old behaviour: straight vs crossed only)")
    ap.add_argument("--swap-strong-margin", type=float, default=0.25,
                    help="crossed better by this much -> swap on the FIRST clean check (no voting)")
    ap.add_argument("--refresh-every-s", type=float, default=120,
                    help="frozen mode: every this many seconds each person may learn 1 new sample (0 = off)")
    ap.add_argument("--refresh-accept-dist", type=float, default=0.20,
                    help="refresh sample must be this close to its own ID")
    ap.add_argument("--refresh-margin", type=float, default=0.10,
                    help="... and every other ID must be at least this much further away")
    ap.add_argument("--refresh-min-conf", type=float, default=0.70, help="min detection confidence")
    ap.add_argument("--refresh-settle-s", type=float, default=30,
                    help="no refresh this long after an ID was (re)bound / swapped / moved")
    ap.add_argument("--long-gap-s", type=float, default=60,
                    help="an ID absent at least this long needs a CLEAR match before it is given to a new track "
                         "(0 = off; operator pool only)")
    ap.add_argument("--long-gap-strong", type=float, default=0.16,
                    help="... a match at or below this distance is always clear enough")
    ap.add_argument("--long-gap-margin", type=float, default=0.06,
                    help="... otherwise it must beat the second-best ID by at least this much")
    ap.add_argument("--apart-frames", type=int, default=5,
                    help="a track seen this many frames on screen far from person P (not overlapping) "
                         "can never take P's ID when P is hidden briefly (0 = off)")
    ap.add_argument("--apart-dist", type=float, default=0.08, help="'far apart' = feet farther than this (diag fraction)")
    ap.add_argument("--apart-iou", type=float, default=0.05, help="... and boxes overlapping less than this")
    ap.add_argument("--apart-fit-margin", type=float, default=0.03,
                    help="not applied if the old holder fitted the ID worse than the new track by more than this")
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
    tracks_f.write("frame,time_s,global_id,track_id,state,x1,y1,x2,y2,w,h,cx,cy,foot_x,foot_y,conf,app_dist,"
                   "next_id,next_dist\n")
    events_f = open(out_dir / f"{stem}_events.txt", "w")

    track_events: dict[int, tuple] = {}  # track id -> (frame, reason) for the overlay
    recent_events: deque = deque(maxlen=6)

    def log(fi, msg):
        line = f"[frame {fi:6d} | {fi / fps:8.2f}s] {msg}"
        events_f.write(line + "\n")
        events_f.flush()
        print(line)
        if msg.split()[0] in ("NEW", "RELINK", "MOVE", "SWAP", "UNLABEL", "UNKNOWN"):
            recent_events.append((fi, msg))
            m = re.search(r"tracks? (\d+)(?:,(\d+))?", msg)
            if m:
                for t in m.groups():
                    if t:
                        track_events[int(t)] = (fi, msg)

    mgr = GlobalIDManager(fps, W, H, args, log)
    trails: dict[int, deque] = {}
    stop = {"flag": False}
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__("flag", True))

    fi, t0 = 0, time.time()
    log(0, f"source={args.source} {W}x{H}@{fps:.1f}fps tracker_yaml={yaml_path}")
    log(0, f"reid={args.reid_model or type(encoder).__name__} gallery={args.gallery_mode} "
           f"assign_app_max={args.assign_app_max} keep_dist={args.keep_dist} unlabel_dist={args.unlabel_dist} "
           f"verify={args.verify_votes}/{args.verify_window} learn_s={args.learn_s} verify_after_s={args.verify_after_s} "
           f"stable={args.stable_s}s/{args.stable_margin} partial_h={args.partial_h_ratio} max_radius={args.max_radius}")
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
            nid, nd = -1, -1.0
            if gid > 0 and mgr.people[gid].last_check and mgr.people[gid].last_check[0] == fi:
                _, _, nid, nd = mgr.people[gid].last_check
                nid = -1 if nid is None else nid
            tracks_f.write(f"{fi},{ts:.3f},{gid},{lid},{state},{x1:.1f},{y1:.1f},{x2:.1f},{y2:.1f},"
                           f"{x2 - x1:.1f},{y2 - y1:.1f},{(x1 + x2) / 2:.1f},{(y1 + y2) / 2:.1f},"
                           f"{fx:.1f},{fy:.1f},{cf:.3f},{d:.3f},{nid},{nd:.3f}\n")
            col = color_for(gid)
            p1, p2 = (int(x1), int(y1)), (int(x2), int(y2))
            cv2.rectangle(vis, p1, p2, col, 2)
            label = pid_name(gid) if gid > 0 else f"? t{lid}"
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
        if DEBUG_OVERLAY:
            draw_debug(vis, fi, results, boxes, confs, mgr, args, track_events, recent_events)
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
        log(fi, f"{pid_name(p.gid)}: first={p.first_frame / fps:.1f}s last={p.last_frame / fps:.1f}s "
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