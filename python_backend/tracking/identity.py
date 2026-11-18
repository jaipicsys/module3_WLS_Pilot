"""
Identity layer: tracker ids (from BoT-SORT) -> stable person ids P1, P2, ...

BoT-SORT keeps a track id through short gaps using motion. When it gives up and starts a NEW
track id, this layer compares the OSNet embedding of the new track with the stored appearance
(gallery) of people who are currently lost, and RE-LINKS the new track to the same person if
the appearance matches.

Appearance distance = 1 - mean(top-3 cosine similarities to the person's gallery).
Same person is usually ~0.10-0.23, different people ~0.27-0.45 (check on your camera).

Events via log(kind, gid, extra):  NEW, RELINK, LOST, UNKNOWN.   Only numpy needed.
"""
import numpy as np


def l2n(v):
    return v / (np.linalg.norm(v) + 1e-12)


def iou_matrix(a, b):
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)), dtype=np.float32)
    x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2])
    y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    aa = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    ab = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / (aa[:, None] + ab[None, :] - inter + 1e-9)


class Person:
    def __init__(self, gid, frame, box):
        self.gid = gid
        self.tid = None              # current tracker id, None = lost
        self.last_frame = frame
        self.last_box = np.asarray(box, dtype=float).copy()
        self.gallery = []            # embeddings of different views
        self.frames_seen = 0
        self.last_suspect = -999     # frame of the last SUSPECT log for this person

    def dist(self, q, topk=3):
        if not self.gallery or q is None:
            return 1.0
        sims = np.asarray(self.gallery) @ q
        k = min(topk, len(sims))
        return float(1.0 - np.sort(sims)[-k:].mean())


class Pending:
    def __init__(self, tid, frame):
        self.tid = tid
        self.first_frame = frame
        self.last_seen = frame
        self.frames = 0
        self.embs = []
        self.confs = []


class IdentityManager:
    def __init__(self, cfg, log, passthrough=False):
        self.log = log
        self.passthrough = passthrough          # True = ReID OFF: tracker ids are used as they are
        self.assign_max = cfg["reid_assign_max"]
        self.new_min = cfg["reid_new_id_min"]
        self.accept = cfg["reid_gallery_accept"]
        self.dedup = cfg["reid_gallery_dedup"]
        self.rank_margin = cfg["reid_rank_margin"]
        self.confirm_frames = cfg["confirm_frames"]
        self.confirm_min_conf = cfg["confirm_min_conf"]
        self.max_ids = cfg["max_ids"]           # 0 = no limit
        self.gallery_size = cfg["gallery_size"]
        self.learn_min = cfg["gallery_learn_min"]
        self.gallery_every = cfg["gallery_every"]
        self.occlusion_iou = cfg["occlusion_iou"]
        self.lost_after = cfg["lost_after_frames"]

        self.people = {}
        self.local2gid = {}
        self.pending = {}
        self.next_gid = 1

    def reset_tracks(self):
        """Stream restarted: tracker ids are gone, but keep who we know (galleries)."""
        self.local2gid.clear()
        self.pending.clear()
        for p in self.people.values():
            p.tid = None

    def _learn(self, p, e):
        if e is None:
            return
        if p.gallery:
            if float((np.asarray(p.gallery) @ e).max()) > self.dedup:
                return                                   # near-duplicate view
            if len(p.gallery) >= self.learn_min and p.dist(e) > self.accept:
                return                                   # does not look like this person
        p.gallery.append(e)
        if len(p.gallery) > self.gallery_size:
            del p.gallery[self.learn_min]                # keep the first views as anchors

    def _check_suspect(self, fi, t, p, e, d):
        """Diagnosis only (nothing is changed): a linked track whose picture fits ANOTHER person
        clearly better than its own id -> probably the tracker swapped two people."""
        if d is None or fi - p.last_suspect < 30:
            return False
        best = None
        for g, q in self.people.items():
            if g == p.gid or not q.gallery:
                continue
            d2 = q.dist(e)
            if best is None or d2 < best[1]:
                best = (g, d2)
        if best and best[1] <= self.assign_max and best[1] < d - 0.10:
            p.last_suspect = fi
            self.log("SUSPECT", p.gid,
                     f"track {t} is P{p.gid} (d={d:.2f}) but looks like P{best[0]} (d={best[1]:.2f})")
            return True
        return False

    def _bind(self, p, tid, box, fi):
        p.tid = tid
        self.local2gid[tid] = p.gid
        p.last_box = np.asarray(box, dtype=float).copy()
        p.last_frame = fi

    def _mark_lost(self, fi, seen):
        for p in self.people.values():
            if p.tid is not None and p.tid not in seen and fi - p.last_frame > self.lost_after:
                self.local2gid.pop(p.tid, None)
                p.tid = None
                self.log("LOST", p.gid, "")

    def update(self, fi, tids, boxes, confs, embed_fn):
        """Returns one (gid or -1, state, appearance_dist or None) per input box."""
        n = len(tids)
        out = [None] * n
        seen = set(tids)

        if self.passthrough:
            for i, t in enumerate(tids):
                p = self.people.get(t)
                if p is None:
                    p = self.people[t] = Person(t, fi, boxes[i])
                    self.log("NEW", t, "(tracker id)")
                elif p.tid is None:
                    self.log("RELINK", t, "(tracker kept the id)")
                p.tid, p.last_frame, p.last_box = t, fi, np.asarray(boxes[i], dtype=float)
                out[i] = (t, "tracked", None)
            self._mark_lost(fi, seen)
            return out

        if n > 1:
            ious = iou_matrix(boxes, boxes)
            np.fill_diagonal(ious, 0)
            clean = ious.max(axis=1) < self.occlusion_iou
        else:
            clean = np.ones(n, dtype=bool)

        need = []
        for i, t in enumerate(tids):
            if t in self.local2gid:
                if clean[i] and fi % self.gallery_every == 0:
                    need.append(i)
            elif clean[i] or t not in self.pending or not self.pending[t].embs:
                need.append(i)
        embs = {}
        if need:
            for i, e in zip(need, embed_fn(boxes[need])):
                embs[i] = e

        ready = []
        for i, t in enumerate(tids):
            if t in self.local2gid:                       # already linked
                p = self.people[self.local2gid[t]]
                p.last_frame, p.last_box = fi, np.asarray(boxes[i], dtype=float)
                p.frames_seen += 1
                e = embs.get(i)
                d = p.dist(e) if (e is not None and p.gallery) else None
                if e is not None:
                    suspect = self._check_suspect(fi, t, p, e, d)
                    if not suspect:                       # never learn from a view that may be someone else
                        self._learn(p, e)
                out[i] = (p.gid, "tracked", d)
            else:                                         # new / unknown tracker id
                pend = self.pending.get(t)
                if pend is None:
                    pend = self.pending[t] = Pending(t, fi)
                pend.frames += 1
                pend.last_seen = fi
                pend.confs.append(float(confs[i]))
                e = embs.get(i)
                if e is not None and (clean[i] or not pend.embs):
                    pend.embs.append(e)
                    if len(pend.embs) > 30:
                        pend.embs.pop(0)
                if (pend.frames >= self.confirm_frames and pend.embs
                        and np.median(pend.confs[-self.confirm_frames:]) >= self.confirm_min_conf):
                    ready.append(i)
                out[i] = (-1, "pending", None)

        self._mark_lost(fi, seen)
        for t in list(self.pending):
            if t not in seen and fi - self.pending[t].last_seen > self.confirm_frames:
                del self.pending[t]                       # flicker / false positive

        bound_now = set()
        for i in ready:
            t = tids[i]
            if t in self.pending:
                self._resolve(fi, i, t, boxes[i], out, bound_now)
        return out

    def _resolve(self, fi, i, t, box, out, bound_now):
        pend = self.pending[t]
        q = l2n(np.mean(pend.embs, axis=0))
        all_d = {g: p.dist(q) for g, p in self.people.items() if p.gallery}
        free = {g: d for g, d in all_d.items()
                if self.people[g].tid is None and g not in bound_now}
        occupied_best = min((d for g, d in all_d.items() if self.people[g].tid is not None),
                            default=9.0)

        if free:
            g, d = min(free.items(), key=lambda kv: kv[1])
            # appearance must pass on its own; and nobody on screen may look clearly closer
            if d <= self.assign_max and occupied_best >= d - self.rank_margin:
                del self.pending[t]
                p = self.people[g]
                for e in pend.embs:
                    self._learn(p, e)
                gap = fi - p.last_frame
                self._bind(p, t, box, fi)
                bound_now.add(g)
                self.log("RELINK", g, f"track {t} -> P{g}  app_dist={d:.2f}  gap={gap} frames")
                out[i] = (g, "relinked", d)
                return

        nearest = min(all_d.items(), key=lambda kv: kv[1]) if all_d else None
        can_add = self.max_ids == 0 or len(self.people) < self.max_ids
        if can_add and (nearest is None or nearest[1] > self.new_min):
            del self.pending[t]
            p = Person(self.next_gid, fi, box)
            self.next_gid += 1
            for e in pend.embs:
                self._learn(p, e)
            self.people[p.gid] = p
            self._bind(p, t, box, fi)
            bound_now.add(p.gid)
            extra = f"track {t}" + (f"  nearest P{nearest[0]} d={nearest[1]:.2f}" if nearest else "")
            self.log("NEW", p.gid, extra)
            out[i] = (p.gid, "new", None)
            return

        if pend.frames == self.confirm_frames or pend.frames % 100 == 0:
            why = (f"nearest P{nearest[0]} d={nearest[1]:.2f} "
                   f"({'on screen' if self.people[nearest[0]].tid is not None else 'lost'})"
                   if nearest else "no galleries yet")
            self.log("UNKNOWN", -1, f"track {t}: {why}")
        out[i] = (-1, "unknown", nearest[1] if nearest else None)