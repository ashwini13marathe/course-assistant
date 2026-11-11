"""Rebuild the demo runtime.

    python scripts/reset.py                 # before_hw3 (HW3 published live)
    python scripts/reset.py --preset after_hw3
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from harness.runtime import default_runtime_root  # noqa: E402
from harness.seed import PRESETS, reset  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--preset", choices=PRESETS, default="before_hw3")
    parser.add_argument("--root", type=Path, default=default_runtime_root())
    args = parser.parse_args()
    rt = reset(args.root, args.preset)
    print(f"Reset {rt.root} with preset {args.preset}.")


if __name__ == "__main__":
    main()
