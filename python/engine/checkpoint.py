"""Checkpoints for the factor engine: save the COMPLETE state of a run so it can be stopped safely and resumed, or
restarted ("branched") from any saved moment.

What is saved: every tensor on the World (worms, genomes, energy, ids, food, ...), every tensor inside every factor
(infections, predator positions, gut contents, fields, ...), the random-number generator, the tick, the measurements so
far, and how many genealogy rows were already written. Files: results/<run>_ckpt/t<tick>.pt (+ latest.txt).

Used by run.py:  automatic resume after an interruption; --from-tick T to branch from a saved tick (Lenski-style
replay: same world, same moment, new luck).
"""
from pathlib import Path

import torch


def _tensors(obj, depth=0):
    """All tensors in an object's attributes, recursing into plain helper objects (e.g. Field) up to depth 2."""
    out = {}
    for k, v in vars(obj).items():
        if k in ("p", "factors", "cfg", "tree_log", "params", "gen"):
            continue
        if torch.is_tensor(v):
            out[k] = v
        elif depth < 2 and hasattr(v, "__dict__") and not isinstance(v, type) and type(v).__module__ != "builtins":
            sub = _tensors(v, depth + 1)
            if sub:
                out[k] = sub
    return out


def _restore(obj, saved, dev):
    for k, v in saved.items():
        if isinstance(v, dict):
            _restore(getattr(obj, k), v, dev)
        else:
            setattr(obj, k, v.to(dev))


def save(w, series, tree_rows, path):
    state = dict(t=w.t, world=_tensors(w), factors=[_tensors(f) for f in w.factors],
                 factor_names=[f.name for f in w.factors], gen=w.gen.get_state(), series=series, tree_rows=tree_rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp"); torch.save(state, tmp); tmp.replace(path)
    (path.parent / "latest.txt").write_text(path.name)


def load(w, path, reseed=None):
    """Load a checkpoint into a freshly built World (same form). reseed: new random seed (branching) or None (exact
    continuation)."""
    from engine import unpack, DEV
    st = torch.load(path, weights_only=False)
    if st["factor_names"] != [f.name for f in w.factors]:
        raise ValueError(f"checkpoint factors {st['factor_names']} don't match this form's {[f.name for f in w.factors]}")
    _restore(w, st["world"], DEV)
    for f, saved in zip(w.factors, st["factors"]):
        _restore(f, saved, DEV)
    w.t = st["t"]; w.p = unpack(w.G)
    if reseed is None:
        w.gen.set_state(st["gen"])
    else:
        w.gen.manual_seed(int(reseed))
    return st["series"], st["tree_rows"]


def latest(ckpt_dir):
    f = Path(ckpt_dir) / "latest.txt"
    return (Path(ckpt_dir) / f.read_text().strip()) if f.exists() else None
