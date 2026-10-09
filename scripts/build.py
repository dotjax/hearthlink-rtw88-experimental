#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare a checked rtw88 source copy and optionally build its USB module."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


DRIVER_PATH = Path("drivers/net/wireless/realtek/rtw88")


def checked_inputs(source, baseline):
    """Read/hash every copied input once, so later source edits cannot slip in."""
    inputs = {}
    for name, expected in baseline["source_file_sha256"].items():
        relative = Path(name)
        if relative.parent != DRIVER_PATH or not (
                relative.suffix == ".h" or relative.name == "usb.c"):
            raise ValueError(f"unsupported source input: {name}")
        content = (source / relative).read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f"baseline mismatch: {name}; review/rebase this source")
        inputs[relative] = content
    return inputs


def checked_kernel_release(kdir, expected):
    symvers = kdir / "Module.symvers"
    if not symvers.is_file() or not symvers.stat().st_size:
        raise ValueError("--kdir must have nonempty matching Module.symvers")
    header = (kdir / "include/generated/utsrelease.h").read_text()
    match = re.search(r'^#define UTS_RELEASE "([^"\n]+)"$', header, re.MULTILINE)
    if not match or match[1] != expected:
        raise ValueError(f"kernel headers must target {expected}")
    return match[1]


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
    manifest_content = (repo / "SOURCE.json").read_bytes()
    baseline = json.loads(manifest_content)
    inputs = checked_inputs(source, baseline)
    patches = []
    for name in (repo / "patches" / f"series-{args.variant}").read_text().splitlines():
        if not name or name.startswith("#"):
            continue
        if Path(name).name != name or not name.endswith(".patch"):
            raise ValueError(f"invalid patch series entry: {name}")
        patches.append(repo / "patches" / name)
    if not patches:
        raise ValueError("patch series is empty")
    for executable in (("patch",) if args.prepare_only else ("patch", "make")):
        if shutil.which(executable) is None:
            parser.error(f"required command missing: {executable}")
    kdir = args.kdir.resolve(strict=True) if args.kdir is not None else None
    release = checked_kernel_release(kdir, baseline["tested_kernel_release"]) if kdir else None
    # Read patches before reserving output; missing inputs leave no partial build.
    patch_content = {p.name: p.read_bytes() for p in patches}
    patch_hashes = {name: hashlib.sha256(content).hexdigest()
                    for name, content in patch_content.items()}
    output.mkdir(parents=True, exist_ok=False)
    driver = output / "source" / DRIVER_PATH
    driver.mkdir(parents=True)
    # Copy verified inputs only: no stale objects or source-supplied Kbuild files.
    for relative, content in inputs.items():
        (output / "source" / relative).write_bytes(content)
    (output / "patches").mkdir()
    for patch in patches:
        snapshot = output / "patches" / patch.name
        snapshot.write_bytes(patch_content[patch.name])
        subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(snapshot)],
                       cwd=output / "source", check=True)
    (driver / "Makefile").write_text(
        "# SPDX-License-Identifier: GPL-2.0-only\n"
        "obj-m += rtw88_usb.o\nrtw88_usb-y := usb.o\n")
    print(f"Prepared {args.variant}: {driver}", flush=True)
    record = {"variant": args.variant, "kernel_release": release,
              "source_manifest_sha256": hashlib.sha256(manifest_content).hexdigest(),
              "patch_sha256": patch_hashes, "compiled": False}
    if kdir:
        record["module_symvers_sha256"] = hashlib.sha256((kdir / "Module.symvers").read_bytes()).hexdigest()
    record_path = output / "build-info.json"
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    if not args.prepare_only:
        started = time.monotonic()
        subprocess.run(["make", "-C", str(kdir), f"M={driver}",
                        f"-j{args.jobs}", "W=1", "modules"], check=True)
        module = driver / "rtw88_usb.ko"
        record.update(compiled=True, build_seconds=round(time.monotonic() - started, 3),
                      module_sha256=hashlib.sha256(module.read_bytes()).hexdigest())
        record_path.write_text(json.dumps(record, indent=2) + "\n")
        print(f"Built module: {driver / 'rtw88_usb.ko'}")
        print("Nothing installed or loaded.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        sys.exit(1)
