# Test record

Recorded October 9, 2026. **Experimental; not a stable release.**

## Baseline and symptoms

RTL8822BU on USB 3, `rtw88_8822bu`/`rtw88_usb`, firmware 30.20.0,
Debian kernel `7.2.8+deb14-amd64`, source package `7.2.8-1`.
AP: 5 GHz channel 36, 20 MHz, WPA3, protected management frames, client isolation.

The AP stopped accepting clients. Logs included firmware TX-report failures,
`error beacon valid`, and reserved-page/firmware download failures. A firmware
update and kernel upgrade had not ended the reported problem. USB reset
restored activation when an ordinary restart failed. The local firmware
page-pool state was not measured; the exact causal diagnosis remains unresolved.

## Build checks

- Matching source/build packages were authenticated Debian APT downloads,
  extracted into a private workspace.
- Both variants compiled and linked with GCC 16, `W=1`, matching
  `Module.symvers`, and BTF using pahole 1.32.
- Patches applied sequentially with zero fuzz; resulting files matched compiled
  source.
- Kernel `checkpatch.pl --no-tree --no-signoff`: zero errors/warnings for all
  three local patch drafts. No new DCO sign-offs were added.
- The USB private structure is allocated inside the USB module; no chip/core
  exported ABI change was intended.
- The repository build helper was then used to rebuild both variants
  successfully. Its output source matched the historical build source exactly;
  it also rejected an altered baseline and refused to overwrite an existing
  build directory.

## Follow-up tooling review

A second review on October 9 found that the original helper hashed only
`usb.c`/`usb.h` while copying unchecked shared headers. An altered `main.h`
layout was accepted in an isolated prepare-only reproduction. The corrected
helper verifies all 41 copied source/header inputs and copies only their checked
bytes. It excludes stale objects and source-supplied build files, checks the
target kernel release, and records build provenance in `build-info.json`.
The altered-header reproduction now fails before creating output.

Both variants were rebuilt successfully after these changes. Their `usb.c` and
`usb.h` still match the earlier experimental builds exactly. Eleven helper
regression tests passed, including changed headers, stale build files, wrong
kernel headers, reset/unavailable traffic counters, and journal permission/no-match
handling. The new diagnostic helper produced a read-only snapshot on the tested
adapter. These checks are not additional hardware tests of the experimental
driver. No new module was loaded and no throughput improvement was measured.

The temporary-load documentation now explicitly reloads required dependencies
before `insmod`, since `modprobe -r` may remove unused dependencies.

## Temporary queue-only test

At 03:01:33 CDT on October 9, patches 0001 and 0002 were loaded as an unsigned
external module. The loaded GNU build ID matched the queue-only artifact.
Out-of-tree/unsigned kernel taint was expected.

The AP was stopped, chip/USB modules unloaded, the adapter reset, the test USB
module inserted, the stock chip module reloaded, and the AP reactivated.
The signed stock module on disk was preserved; no persistent override was
installed. Reboot therefore restores the stock module in this setup.

No new rtw88 errors, kernel warnings, or Oops appeared during the short journal
interval checked after activation. Local DNS/HTTPS checks passed; firewall,
VPN, and DNS configuration checks confirmed no changes during the test.
The initial automated check preceded client association. Subsequently the human
tester reported **“It works!”**, confirming working Wi-Fi for them.
No quantitative throughput or repeated-reconnection result was captured from
that confirmation. The accompanying USB reset is a confounding intervention.

Historical test-module SHA-256:
`5483377725701be90bd71551ecf173f38de73ac899e1d28b708614815e65f690`.
This identifies that artifact; rebuilds may differ due to build-path/toolchain
metadata. The binary is not published here.

## Remaining tests

Patch 0003 was compiled and its lifetime paths reviewed, but **not loaded or
hardware-tested**. Neither variant has timeout/disconnect fault-injection,
long-duration stability, throughput, multi-client, or repeatable sleep/wake
results recorded.

For further tests, record kernel/source/firmware, USB mode, AP configuration,
variant, client model, start/end time, and whether reset occurred. Compare stock
and patched drivers with the same reset and traffic procedure before attributing
improvement. Exercise reconnects, sleeping clients, multicast/broadcast, DHCP,
multiple clients, and several hours of use. Keep wired/console recovery access.
Evaluate the combined variant separately and sanitize public diagnostics.
