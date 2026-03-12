"""
IPL Analytics — Data Preprocessing Pipeline Orchestrator
Run this once whenever the raw data is updated.

Usage: python data/preprocessing/run_pipeline.py
"""

import time
import subprocess
import sys
from pathlib import Path

PIPELINE_DIR = Path(__file__).parent
SCRIPTS = [
    ("01_clean.py", "CLEANING RAW DATA"),
    ("02_derive_features.py", "DERIVING FEATURES"),
    ("03_build_aggregates.py", "BUILDING AGGREGATES"),
]


def run_step(script_name, description):
    """Run a pipeline step as a subprocess."""
    script_path = PIPELINE_DIR / script_name
    if not script_path.exists():
        print(f"  ⚠ {script_name} not found — skipping")
        return False

    print(f"\n{'='*60}")
    print(f"  [{description}] Running {script_name}...")
    print(f"{'='*60}")

    start = time.time()
    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        cwd=str(PIPELINE_DIR.parent.parent),  # project root
    )

    elapsed = time.time() - start

    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print(f"  ❌ FAILED in {elapsed:.1f}s")
        if result.stderr:
            print(f"  ERROR: {result.stderr}")
        return False

    print(f"  ✅ Completed in {elapsed:.1f}s")
    return True


def main():
    print("=" * 60)
    print("  🏏 IPL ANALYTICS DATA PIPELINE")
    print("=" * 60)

    total_start = time.time()
    success = True

    for i, (script, desc) in enumerate(SCRIPTS, 1):
        step_label = f"{i}/{len(SCRIPTS)} {desc}"
        if not run_step(script, step_label):
            success = False
            print(f"\n❌ Pipeline failed at step {i}. Fix errors and re-run.")
            break

    total_elapsed = time.time() - total_start
    print(f"\n{'='*60}")
    if success:
        print(f"  ✅ PIPELINE COMPLETE in {total_elapsed:.1f}s")
    else:
        print(f"  ❌ PIPELINE FAILED after {total_elapsed:.1f}s")
    print(f"{'='*60}")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
