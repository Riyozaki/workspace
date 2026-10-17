"""Tool-visible timestamps and append-only research stage logging."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]


def stamp(stage: str, note: str = "") -> dict:
    start = json.loads((ROOT / "research/start_time.json").read_text())
    elapsed = time.time() - start["start_unix"]
    monotonic_elapsed = time.monotonic() - start["start_monotonic"]
    result = {"utc": datetime.now(timezone.utc).isoformat(),
              "elapsed_seconds": elapsed, "elapsed_monotonic_seconds": monotonic_elapsed,
              "remaining_seconds": max(0.0, 5400 - min(elapsed, monotonic_elapsed)),
              "stage": stage, "budget_elapsed": min(elapsed, monotonic_elapsed) >= 5400}
    with (ROOT / "work_log.md").open("a") as f:
        f.write(f'\n## {stage}\n\n- Tool time: {result["utc"]}; elapsed {elapsed:.3f} s; '
                f'remaining {result["remaining_seconds"]:.3f} s.\n')
        if note:
            f.write(f"- {note}\n")
    print(json.dumps(result, indent=2), flush=True)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("stage")
    p.add_argument("--note", default="")
    p.add_argument("--require-deadline", action="store_true")
    a = p.parse_args()
    s = stamp(a.stage, a.note)
    if a.require_deadline and not s["budget_elapsed"]:
        raise SystemExit("The 90-minute deadline has NOT elapsed: no final report yet.")
