#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read-only rtw88 health snapshot; no root requests or network traffic."""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import time


STAT_NAMES = ("rx_bytes", "tx_bytes", "rx_packets", "tx_packets",
              "rx_errors", "tx_errors", "rx_dropped", "tx_dropped")
ERROR_PATTERNS = {
    "tx_report_failure": r"failed to get tx report",
    "beacon_valid_failure": r"error beacon valid",
    "reserved_page_failure": r"failed to (?:download|write).*rsvd page",
    "firmware_download_failure": r"failed to download firmware",
    "usb_error": r"usb.*(?:error|fail)|device descriptor.*error",
}


def read_optional(path):
    try:
        return path.read_text().strip()
    except OSError:
        return None


def read_stats(net):
    values = {}
    for name in STAT_NAMES:
        value = read_optional(net / "statistics" / name)
        values[name] = int(value) if value is not None and value.isdecimal() else None
    return values


def traffic_rates(before, after, seconds):
    rates = {}
    for name in ("rx_bytes", "tx_bytes"):
        first, last = before.get(name), after.get(name)
        rates[name.replace("_bytes", "_mbit_per_second")] = (
            round((last - first) * 8 / seconds / 1_000_000, 3)
            if first is not None and last is not None and last >= first and seconds > 0
            else None)
    return rates


def usb_parent(net):
    device = (net / "device").resolve()
    for parent in (device, *device.parents):
        if (parent / "idVendor").is_file() and (parent / "idProduct").is_file():
            return parent
    return None


def build_id(path):
    try:
        data = path.read_bytes()
        namesz, descsz, kind = struct.unpack_from("=III", data)
        offset = 12 + ((namesz + 3) & ~3)
        if kind == 3 and data[12:12 + namesz].rstrip(b"\0") == b"GNU":
            if offset + descsz <= len(data):
                return data[offset:offset + descsz].hex()
    except (OSError, struct.error):
        pass
    return None


def executable(name):
    found = shutil.which(name)
    if found:
        return found
    for directory in ("/usr/sbin", "/sbin"):
        path = Path(directory) / name
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    return None


def driver_info(interface):
    ethtool = executable("ethtool")
    if not ethtool:
        return {"available": False}
    try:
        result = subprocess.run([ethtool, "-i", interface], text=True,
                                capture_output=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False}
    if result.returncode:
        return {"available": False}
    fields = dict(line.split(":", 1) for line in result.stdout.splitlines() if ":" in line)
    return {"available": True, "driver": fields.get("driver", "").strip(),
            "firmware_version": fields.get("firmware-version", "").strip()}


def count_errors(text):
    return {name: sum(bool(re.search(pattern, line, re.IGNORECASE))
                      for line in text.splitlines())
            for name, pattern in ERROR_PATTERNS.items()}


def journal_summary(since, usb):
    journalctl = executable("journalctl")
    if not journalctl:
        return {"available": False, "reason": "journalctl unavailable"}
    pattern = r"rtw(?:88|_)"
    if usb:
        pattern += "|usb " + re.escape(usb.name) + r"(?=[: ])"
    try:
        result = subprocess.run([journalctl, "-k", "--since", since, "--grep", pattern,
                                 "--no-pager", "-o", "cat"], text=True,
                                capture_output=True, timeout=10,
                                env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False, "reason": "journal read failed or timed out"}
    # journalctl --grep uses exit 1 for an empty match set as well as errors.
    empty_output = result.stdout.strip() in ("", "-- No entries --")
    no_matches = result.returncode == 1 and empty_output and not result.stderr.strip()
    if result.returncode and not no_matches:
        return {"available": False, "reason": "journal query failed"}
    limited = bool(re.search(r"not seeing|permission|access denied|no journal",
                             result.stderr, re.IGNORECASE))
    messages = "" if empty_output else result.stdout
    return {"available": True, "permission_warning": limited, "since": since,
            "scope": "rtw88 family and selected USB device; not per-interface attribution",
            "matched_messages": len(messages.splitlines()),
            "error_counts": count_errors(messages)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", required=True)
    parser.add_argument("--since", default="15 minutes ago", help="journal time window")
    parser.add_argument("--sample-seconds", type=float, default=0,
                        help="passive traffic sample, 0 to 30 seconds; no traffic generated")
    parser.add_argument("--output", type=Path, help="new private JSON file; default: stdout")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,15}", args.interface) or args.interface in (".", ".."):
        parser.error("invalid interface name")
    if not math.isfinite(args.sample_seconds) or not 0 <= args.sample_seconds <= 30:
        parser.error("--sample-seconds must be finite and between 0 and 30")
    net = Path("/sys/class/net") / args.interface
    if not net.exists():
        parser.error("interface does not exist")
    usb = usb_parent(net)
    module = Path("/sys/module/rtw88_usb")
    report = {"schema_version": 1, "captured_at_utc": datetime.now(timezone.utc).isoformat(),
              "interface": args.interface, "kernel_release": platform.release(),
              "interface_index": read_optional(net / "ifindex"),
              "operstate": read_optional(net / "operstate"),
              "driver": driver_info(args.interface),
              "rtw88_usb": {"loaded": module.is_dir(),
                            "build_id": build_id(module / "notes/.note.gnu.build-id")},
              "usb": None, "counters": read_stats(net)}
    if usb:
        report["usb"] = {name: read_optional(usb / path) for name, path in
                         {"vendor_id": "idVendor", "product_id": "idProduct",
                          "speed_mbit_per_second": "speed", "power_control": "power/control",
                          "runtime_status": "power/runtime_status"}.items()}
    if args.sample_seconds:
        started = time.monotonic()
        time.sleep(args.sample_seconds)
        after = read_stats(net)
        elapsed = time.monotonic() - started
        changed = report["interface_index"] != read_optional(net / "ifindex")
        rates = traffic_rates(report["counters"], after, elapsed)
        if changed:
            rates = {key: None for key in rates}
        report["traffic_sample"] = {"elapsed_seconds": round(elapsed, 3),
                                    "interface_changed": changed, "rates": rates,
                                    "ending_counters": after}
    report["journal"] = journal_summary(args.since, usb)
    content = json.dumps(report, indent=2) + "\n"
    if args.output:
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write(content)
        print(f"Saved read-only report: {args.output}")
    else:
        print(content, end="")


if __name__ == "__main__":
    try:
        main()
    except OSError as error:
        print(f"Diagnostic failed: {error}", file=sys.stderr)
        sys.exit(1)
