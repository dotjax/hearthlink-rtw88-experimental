# SPDX-License-Identifier: GPL-2.0-only
"""Regression tests for ABI input checks and privacy-preserving diagnostics."""

import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess


def load(name):
    script = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load("build")
diagnose = load("diagnose")


class SourceChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.files = {str(build.DRIVER_PATH / "usb.c"): b"usb source\n",
                      str(build.DRIVER_PATH / "usb.h"): b"USB private header\n",
                      str(build.DRIVER_PATH / "main.h"): b"struct rtw_dev {};\n"}
        for name, content in self.files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.baseline = {"source_file_sha256": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in self.files.items()}}

    def test_modified_shared_header_is_rejected(self):
        (self.root / build.DRIVER_PATH / "main.h").write_text("struct rtw_dev { long extra; };\n")
        with self.assertRaisesRegex(ValueError, "baseline mismatch.*main.h"):
            build.checked_inputs(self.root, self.baseline)

    def test_verified_snapshot_survives_later_source_edit(self):
        inputs = build.checked_inputs(self.root, self.baseline)
        (self.root / build.DRIVER_PATH / "main.h").write_text("changed after check\n")
        self.assertEqual(inputs[build.DRIVER_PATH / "main.h"], self.files[str(build.DRIVER_PATH / "main.h")])

    def test_build_files_and_stale_objects_are_not_selected(self):
        (self.root / build.DRIVER_PATH / "Kbuild").write_text("obj-m := unexpected.o\n")
        (self.root / build.DRIVER_PATH / "usb.o").write_bytes(b"stale object")
        inputs = build.checked_inputs(self.root, self.baseline)
        self.assertNotIn(build.DRIVER_PATH / "Kbuild", inputs)
        self.assertNotIn(build.DRIVER_PATH / "usb.o", inputs)

    def test_manifest_cannot_select_outside_driver(self):
        self.baseline["source_file_sha256"]["../outside.h"] = "ignored"
        with self.assertRaisesRegex(ValueError, "unsupported source input"):
            build.checked_inputs(self.root, self.baseline)

    def test_wrong_kernel_release_is_rejected(self):
        (self.root / "Module.symvers").write_text("nonempty fixture\n")
        header = self.root / "include/generated/utsrelease.h"
        header.parent.mkdir(parents=True)
        header.write_text('#define UTS_RELEASE "different-kernel"\n')
        with self.assertRaisesRegex(ValueError, "kernel headers must target"):
            build.checked_kernel_release(self.root, "expected-kernel")

    def test_empty_symbol_table_is_rejected(self):
        (self.root / "Module.symvers").touch()
        with self.assertRaisesRegex(ValueError, "nonempty"):
            build.checked_kernel_release(self.root, "expected-kernel")


class DiagnosticChecks(unittest.TestCase):
    def test_empty_grep_result_is_not_a_journal_failure(self):
        for output in ("", "-- No entries --\n"):
            with self.subTest(output=output):
                with patch.object(diagnose, "executable", return_value="journalctl"), \
                        patch.object(diagnose.subprocess, "run",
                                     return_value=subprocess.CompletedProcess([], 1, output, "")):
                    result = diagnose.journal_summary("15 minutes ago", None)
                self.assertTrue(result["available"])
                self.assertEqual(result["matched_messages"], 0)

    def test_access_failure_has_no_invented_error_counts(self):
        with patch.object(diagnose, "executable", return_value="journalctl"), \
                patch.object(diagnose.subprocess, "run",
                             return_value=subprocess.CompletedProcess([], 1, "", "Permission denied")):
            result = diagnose.journal_summary("15 minutes ago", None)
        self.assertFalse(result["available"])
        self.assertNotIn("error_counts", result)

    def test_counter_reset_has_no_negative_rate(self):
        rates = diagnose.traffic_rates({"rx_bytes": 100, "tx_bytes": 0},
                                       {"rx_bytes": 2, "tx_bytes": 1_000_000}, 2)
        self.assertIsNone(rates["rx_mbit_per_second"])
        self.assertEqual(rates["tx_mbit_per_second"], 4.0)

    def test_unreadable_counter_has_no_invented_zero(self):
        rates = diagnose.traffic_rates({"rx_bytes": None, "tx_bytes": 10},
                                       {"rx_bytes": 100, "tx_bytes": None}, 1)
        self.assertEqual(rates, {"rx_mbit_per_second": None, "tx_mbit_per_second": None})

    def test_error_summary_does_not_return_raw_identifiers(self):
        text = ("rtw_8822bu: error beacon valid client aa:bb:cc:dd:ee:ff\n"
                "rtw_8822bu: failed to get tx report from firmware private-ssid\n")
        summary = diagnose.count_errors(text)
        self.assertEqual(summary["beacon_valid_failure"], 1)
        self.assertEqual(summary["tx_report_failure"], 1)
        self.assertNotIn("private-ssid", str(summary))
        self.assertNotIn("aa:bb", str(summary))


if __name__ == "__main__":
    unittest.main()
