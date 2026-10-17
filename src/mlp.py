"""Minimal float32 NumPy MLP with dropout, AdamW, hard-label and distillation training.

Everything is deliberately explicit: the same forward/backward code is used for the
large baseline and the small student, so latency differences are due to layer sizes,
not to different implementations.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


def he_init(fan_in: int, fan_out: int, rng: np.random.Generator) -> np.ndarray:
    return (rng.standard_normal((fan_in, fan_out)) * np.sqrt(2.0 / fan_in)).astype(np.float32)


def softmax(z: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    zz = z / temperature
    zz = zz - zz.max(axis=1, keepdims=True)
    e = np.exp(zz)
    return e / e.sum(axis=1, keepdims=True)


@dataclass
class MLP:
    sizes: list[int]
    dropout: float = 0.0
    rng: np.random.Generator = field(default_factory=np.random.default_rng)
    W: list[np.ndarray] = field(init=False)
    b: list[np.ndarray] = field(init=False)

    def __post_init__(self) -> None:
        self.W, self.b = [], []
        for i in range(len(self.sizes) - 1):
            self.W.append(he_init(self.sizes[i], self.sizes[i + 1], self.rng))
            self.b.append(np.zeros(self.sizes[i + 1], dtype=np.float32))



def forward(model: MLP, x: np.ndarray, training: bool = False,
            rng: np.random.Generator | None = None):
    """Forward pass. Cache entries are (layer_input, pre_activation, dropout_mask)."""
    caches = []
    h = x
    last = len(model.W) - 1
    for i, (W, b) in enumerate(zip(model.W, model.b)):
        layer_in = h
        z = h @ W + b
        if i < last:
            a = np.maximum(z, 0.0)
            if training and model.dropout > 0.0:
                if rng is None:
                    raise ValueError("rng required for dropout")
                mask = (rng.random(a.shape, dtype=np.float32) >= model.dropout).astype(np.float32)
                mask *= np.float32(1.0 / (1.0 - model.dropout))
                h = a * mask
            else:
                mask = None
                h = a
            caches.append((layer_in, z, mask))
        else:
            caches.append((layer_in, z, None))
    return z, caches


def backward(model: MLP, caches, dlogits: np.ndarray):
    grads_W = [None] * len(model.W)
    grads_b = [None] * len(model.b)
    d = dlogits
    for i in range(len(model.W) - 1, -1, -1):
        layer_in, z, mask = caches[i]
        if i < len(model.W) - 1:
            d = d * (z > 0.0)
            if mask is not None:
                d = d * mask
        grads_W[i] = layer_in.T @ d
        grads_b[i] = d.sum(axis=0)
        if i > 0:
            d = d @ model.W[i].T
    return grads_W, grads_b


class AdamW:
    def __init__(self, model: MLP, lr: float, weight_decay: float = 1e-4,
                 beta1: float = 0.9, beta2: float = 0.999, eps: float = 1e-8):
        self.lr = lr
        self.wd = weight_decay
        self.b1, self.b2, self.eps = beta1, beta2, eps
        self.m = [np.zeros_like(p) for p in model.W + model.b]
        self.v = [np.zeros_like(p) for p in model.W + model.b]
        self.t = 0

    def step(self, model: MLP, grads_W, grads_b, lr: float | None = None) -> None:
        self.t += 1
        lr = self.lr if lr is None else lr
        params = model.W + model.b
        grads = grads_W + grads_b
        bc1 = 1.0 - self.b1 ** self.t
        bc2 = 1.0 - self.b2 ** self.t
        for p, g, m, v in zip(params, grads, self.m, self.v):
            if self.wd:
                p *= np.float32(1.0 - lr * self.wd)
            m *= self.b1
            m += (1.0 - self.b1) * g
            v *= self.b2
            v += (1.0 - self.b2) * (g * g)
            p -= (lr * (m / bc1) / (np.sqrt(v / bc2) + self.eps)).astype(np.float32)


def accuracy(logits: np.ndarray, y: np.ndarray) -> float:
    return float((logits.argmax(axis=1) == y).mean())


def macro_f1(pred: np.ndarray, y: np.ndarray, n_classes: int = 10) -> float:
    f1s = []
    for c in range(n_classes):
        tp = np.sum((pred == c) & (y == c))
        fp = np.sum((pred == c) & (y != c))
        fn = np.sum((pred != c) & (y == c))
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return float(np.mean(f1s))


def expected_calibration_error(probs: np.ndarray, y: np.ndarray, n_bins: int = 15) -> float:
    conf = probs.max(axis=1)
    pred = probs.argmax(axis=1)
    correct = (pred == y).astype(np.float32)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def predict_logits(model: MLP, x: np.ndarray, batch_size: int = 1024) -> np.ndarray:
    out = []
    for i in range(0, len(x), batch_size):
        z, _ = forward(model, x[i:i + batch_size], training=False)
        out.append(z)
    return np.concatenate(out, axis=0)


def evaluate(model: MLP, x: np.ndarray, y: np.ndarray) -> dict[str, float]:
    z = predict_logits(model, x)
    p = softmax(z)
    pred = p.argmax(axis=1)
    return {
        "acc": float((pred == y).mean()),
        "macro_f1": macro_f1(pred, y),
        "ece": expected_calibration_error(p, y),
    }


def distillation_targets(model: MLP, x: np.ndarray, temperature: float,
                         batch_size: int = 2048) -> np.ndarray:
    """Softmax(teacher_logits / T) for every training example."""
    out = []
    for i in range(0, len(x), batch_size):
        z, _ = forward(model, x[i:i + batch_size], training=False)
        out.append(softmax(z, temperature))
    return np.concatenate(out, axis=0)


def train(model: MLP, x, y, *, epochs: int, batch_size: int = 128, lr: float = 1e-3,
          weight_decay: float = 1e-4, soft_targets: np.ndarray | None = None,
          alpha: float = 0.5, temperature: float = 4.0,
          x_val=None, y_val=None, seed: int = 0, log_every_epoch: bool = True,
          time_limit_s: float | None = None):
    """Train in place. Returns history list of dicts."""
    import time
    rng = np.random.default_rng(seed + 10_007)
    opt = AdamW(model, lr=lr, weight_decay=weight_decay)
    n = len(x)
    steps_per_epoch = int(np.ceil(n / batch_size))
    total_steps = steps_per_epoch * epochs
    step = 0
    history = []
    t0 = time.perf_counter()
    for epoch in range(epochs):
        order = rng.permutation(n)
        ep_loss = 0.0
        for bi in range(steps_per_epoch):
            idx = order[bi * batch_size:(bi + 1) * batch_size]
            xb, yb = x[idx], y[idx]
            z, caches = forward(model, xb, training=True, rng=rng)
            p = softmax(z)
            if soft_targets is None:
                onehot = np.zeros_like(p)
                onehot[np.arange(len(yb)), yb] = 1.0
                dlogits = (p - onehot) / len(yb)
            else:
                q = soft_targets[idx]
                pT = softmax(z, temperature)
                onehot = np.zeros_like(p)
                onehot[np.arange(len(yb)), yb] = 1.0
                dlogits = (alpha * (p - onehot) + (1.0 - alpha) * temperature * (pT - q)) / len(yb)
            gw, gb = backward(model, caches, dlogits)
            frac = step / max(1, total_steps - 1)
            cur_lr = lr * (0.01 + 0.99 * 0.5 * (1.0 + np.cos(np.pi * frac)))
            opt.step(model, gw, gb, lr=cur_lr)
            ep_loss += float(-np.log(np.clip(p[np.arange(len(yb)), yb], 1e-9, 1.0)).mean())
            step += 1
        rec = {"epoch": epoch + 1, "train_ce": ep_loss / steps_per_epoch,
               "lr": float(cur_lr), "wall_s": time.perf_counter() - t0}
        if x_val is not None:
            rec["val_acc"] = accuracy(predict_logits(model, x_val), y_val)
        history.append(rec)
        if log_every_epoch:
            print(f"  epoch {epoch + 1:2d}/{epochs}  ce={rec['train_ce']:.3f}  "
                  f"{'val_acc=%.4f  ' % rec['val_acc'] if 'val_acc' in rec else ''}"
                  f"t={rec['wall_s']:.1f}s", flush=True)
        if time_limit_s is not None and rec["wall_s"] > time_limit_s:
            print(f"  [time limit {time_limit_s}s reached, stopping early]", flush=True)
            break
    return history


def count_params(model: MLP) -> int:
    return int(sum(w.size for w in model.W) + sum(b.size for b in model.b))


def forward_flops_per_sample(model: MLP) -> int:
    """MACs counted as FLOPs=2*MAC for matmuls; bias/ReLU/argmax are negligible."""
    macs = 0
    for i, (w, b) in enumerate(zip(model.W, model.b)):
        macs += model.sizes[i] * model.sizes[i + 1]
    return int(2 * macs)


def prune_teacher(teacher: MLP, w1: int, w2: int) -> MLP:
    """Structured neuron pruning by outgoing-weight L2 norm, keeping dense matrices."""
    imp1 = np.linalg.norm(teacher.W[1], axis=1)   # outgoing strength of layer-1 neurons
    imp2 = np.linalg.norm(teacher.W[2], axis=1)   # outgoing strength of layer-2 neurons
    keep1 = np.sort(np.argsort(imp1)[-w1:])
    keep2 = np.sort(np.argsort(imp2)[-w2:])
    student = MLP([teacher.sizes[0], w1, w2, teacher.sizes[-1]],
                  dropout=teacher.dropout, rng=np.random.default_rng(0))
    student.W[0] = teacher.W[0][:, keep1].copy()
    student.b[0] = teacher.b[0][keep1].copy()
    student.W[1] = teacher.W[1][np.ix_(keep1, keep2)].copy()
    student.b[1] = teacher.b[1][keep2].copy()
    student.W[2] = teacher.W[2][keep2, :].copy()
    student.b[2] = teacher.b[2].copy()
    return student


def prune_teacher_random(teacher: MLP, w1: int, w2: int, seed: int = 0) -> MLP:
    """Ablation: identical architecture, but kept neurons chosen at random (no importance score)."""
    rng = np.random.default_rng(seed)
    keep1 = np.sort(rng.choice(teacher.sizes[1], size=w1, replace=False))
    keep2 = np.sort(rng.choice(teacher.sizes[2], size=w2, replace=False))
    student = MLP([teacher.sizes[0], w1, w2, teacher.sizes[-1]],
                  dropout=teacher.dropout, rng=np.random.default_rng(0))
    student.W[0] = teacher.W[0][:, keep1].copy()
    student.b[0] = teacher.b[0][keep1].copy()
    student.W[1] = teacher.W[1][np.ix_(keep1, keep2)].copy()
    student.b[1] = teacher.b[1][keep2].copy()
    student.W[2] = teacher.W[2][keep2, :].copy()
    student.b[2] = teacher.b[2].copy()
    return student
