"""simctl: the link between a running simulation and the watcher settings (python/remote/watcher_settings.toml).

A simulation calls `ctl.after_tick(t, frame_fn)` once per tick. It:
  - re-reads the settings every 2 seconds (changes apply live),
  - applies QUIET MODE (GPU rests a fraction of the time) and SLOW MOTION (tick_delay_ms),
  - every `live.frame_every` ticks writes a LIVE FRAME of one world to python/remote/live/<job>.json
    (what the GUI's live view draws),
  - every `replay.record_every` ticks appends a frame to python/remote/replays/<job>/frames.jsonl (for replay),
    up to `replay.max_frames`.
frame_fn(world_index, max_worms) must return a small dict: {"size": arena size, "worms": [[x, y, kind], ...],
"food": [[x, y, amount], ...], "extra": {...}}; it is only called when a frame is due.
The job name comes from the environment variable SIM_JOB (set by the watcher) or the given default.
Everything is best-effort: if a file can't be written, the simulation keeps running.
"""
import json, os, time, tomllib
from pathlib import Path

REMOTE = Path(__file__).resolve().parent
SETTINGS = REMOTE / "watcher_settings.toml"
DEFAULTS = {"speed": {"quiet": 0.0, "tick_delay_ms": 0},
            "live": {"enabled": True, "frame_every": 20, "world": 0, "max_worms_drawn": 640},
            "replay": {"record": True, "record_every": 200, "max_frames": 5000}}


# Allowed ranges for every editable setting. The GUI rejects values outside them and the watcher clamps to them, so
# no setting can be made dangerous for the computer (e.g. a hard temperature stop above 92 C).
SETTING_RANGES = {
    ("display", "theme"): ["system", "light", "dark"], ("display", "refresh_seconds"): (1, 60),
    ("jobs", "max_parallel"): (1, 4), ("jobs", "util_max"): (10, 90), ("jobs", "max_wait_minutes"): (1, 1440),
    ("safety", "start_temp_max"): (50, 83), ("safety", "overheat_temp"): (60, 88), ("safety", "overheat_seconds"): (10, 600),
    ("safety", "hard_temp_stop"): (65, 92), ("safety", "vram_margin_mb"): (500, 6000),
    ("safety", "min_disk_gb_start"): (2, 500), ("safety", "min_disk_gb_run"): (0.5, 100),
    ("safety", "min_ram_gb_start"): (1, 64), ("safety", "min_ram_gb_run"): (0.25, 32),
    ("speed", "quiet"): (0.0, 0.9), ("speed", "tick_delay_ms"): (0, 1000),
    ("live", "enabled"): [True, False], ("live", "frame_every"): (1, 10000), ("live", "world"): (0, 10000),
    ("live", "max_worms_drawn"): (10, 5000),
    ("replay", "record"): [True, False], ("replay", "record_every"): (10, 100000), ("replay", "max_frames"): (10, 100000),
}


def clamp_setting(sec, key, v):
    r = SETTING_RANGES.get((sec, key))
    if r is None:
        return v
    if isinstance(r, list):
        return v if v in r else r[0]
    lo, hi = r
    return type(lo)(min(max(v, lo), hi)) if isinstance(lo, int) and not isinstance(v, float) else min(max(float(v), lo), hi)


def load_settings():
    s = {k: dict(v) for k, v in DEFAULTS.items()}
    try:
        for k, v in tomllib.loads(SETTINGS.read_text()).items():
            s.setdefault(k, {}).update({kk: clamp_setting(k, kk, vv) for kk, vv in v.items()})
    except Exception:
        pass
    return s


class SimControl:
    def __init__(self, default_job="manual", sync=None):
        self.job = os.environ.get("SIM_JOB", default_job)
        self.sync = sync or (lambda: None)          # e.g. torch.cuda.synchronize, so quiet-mode timing is real
        self.s = load_settings(); self.last_read = time.time()
        self.t_busy = time.perf_counter(); self.frames = 0
        (REMOTE / "live").mkdir(exist_ok=True)
        self.rep_dir = REMOTE / "replays" / self.job
        self.live_file = REMOTE / "live" / f"{self.job}.json"

    def after_tick(self, t, frame_fn):
        now = time.time()
        if now - self.last_read > 2:
            self.s = load_settings(); self.last_read = now
        sp, lv, rp = self.s["speed"], self.s["live"], self.s["replay"]
        try:
            if lv.get("enabled") and t % max(1, int(lv["frame_every"])) == 0:
                f = frame_fn(int(lv.get("world", 0)), int(lv.get("max_worms_drawn", 640)))
                f.update(t=t, job=self.job, time=time.strftime("%H:%M:%S"))
                tmp = self.live_file.with_suffix(".tmp"); tmp.write_text(json.dumps(f)); tmp.replace(self.live_file)
            if rp.get("record") and t % max(1, int(rp["record_every"])) == 0 and self.frames < int(rp["max_frames"]):
                f = frame_fn(int(lv.get("world", 0)), int(lv.get("max_worms_drawn", 640)))
                f.update(t=t)
                self.rep_dir.mkdir(parents=True, exist_ok=True)
                with (self.rep_dir / "frames.jsonl").open("a") as fh:
                    fh.write(json.dumps(f) + "\n")
                self.frames += 1
        except Exception:
            pass
        q = float(sp.get("quiet", 0.0)); d = float(sp.get("tick_delay_ms", 0))
        if q > 0 and t % 10 == 0:                       # rest the GPU: sleep q/(1-q) of the busy time
            self.sync(); busy = time.perf_counter() - self.t_busy
            time.sleep(busy * min(q, 0.9) / (1 - min(q, 0.9)))
            self.t_busy = time.perf_counter()
        if d > 0:
            time.sleep(d / 1000)
