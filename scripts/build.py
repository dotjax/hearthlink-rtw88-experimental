#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare a checked rtw88 source copy and optionally build its USB module."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    repo = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="pristine extracted Linux source directory")
    parser.add_argument("--kdir", type=Path,
                        help="prepared matching kernel headers/build directory")
    parser.add_argument("--variant", choices=("queue-only", "queue-and-sync"),
                        default="queue-only")
    parser.add_argument("--output", type=Path,
                        help="new output directory; default: build/VARIANT")
    parser.add_argument("--jobs", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if not args.prepare_only and args.kdir is None:
        parser.error("--kdir is required unless --prepare-only is used")
    source = args.source.resolve(strict=True)
    output = (args.output or repo / "build" / args.variant).resolve()
    if output == source or source in output.parents or output in source.parents:
        parser.error("output and source must be separate directories")
    if output.exists():
        parser.error("output exists; select a fresh --output directory")
    baseline = json.loads((repo / "SOURCE.json").read_text())
    for name, expected in baseline["source_file_sha256"].items():
        actual = hashlib.sha256((source / name).read_bytes()).hexdigest()
        if actual != expected:
            parser.error(f"baseline mismatch: {name}; review/rebase this source")
    patches = [repo / "patches" / "0001-honor-after-dtim.patch",
               repo / "patches" / "0002-bound-after-dtim-queue.patch"]
    if args.variant == "queue-and-sync":
        patches.append(repo / "patches" / "0003-wait-for-reserved-page-usb.patch")
    for executable in (("patch",) if args.prepare_only else ("patch", "make")):
        if shutil.which(executable) is None:
            parser.error(f"required command missing: {executable}")
    kdir = args.kdir.resolve(strict=True) if args.kdir is not None else None
    if not args.prepare_only and not (kdir / "Module.symvers").is_file():
        parser.error("--kdir must have matching Module.symvers")
    driver_path = Path("drivers/net/wireless/realtek/rtw88")
    driver = output / "source" / driver_path
    # Retain the original driver files and their copyright/SPDX notices.
    shutil.copytree(source / driver_path, driver)
    for patch in patches:
        subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(patch)],
                       cwd=output / "source", check=True)
    (driver / "Makefile").write_text(
        "# SPDX-License-Identifier: GPL-2.0-only\n"
        "obj-m += rtw88_usb.o\nrtw88_usb-y := usb.o\n")
    print(f"Prepared {args.variant}: {driver}", flush=True)
    if not args.prepare_only:
        subprocess.run(["make", "-C", str(kdir), f"M={driver}",
                        f"-j{args.jobs}", "W=1", "modules"], check=True)
        print(f"Built module: {driver / 'rtw88_usb.ko'}")
        print("Nothing installed or loaded.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        sys.exit(1)
