# Hearthlink rtw88 experiments

**EXPERIMENTAL — not stable or production-ready.** Linux `rtw88` USB patches
investigated after an RTL8822BU access point stopped accepting clients.
Keep a wired connection or local console and a rollback plan when testing:
experimental kernel modules can crash the host.

The original driver family is `rtw88`; the tested adapter uses
`rtw88_8822bu`. These patches change the shared `rtw88_usb` transport in
`drivers/net/wireless/realtek/rtw88/usb.c` and `usb.h`. Firmware is unchanged.

## Patch sets

| Variant | Patches | Purpose | Local evidence |
| --- | --- | --- | --- |
| `queue-only` | 0001 + 0002 | Honor after-DTIM flag; limit high-queue feed | Built, temporarily loaded; tester reported Wi-Fi working |
| `queue-and-sync` | 0001 + 0002 + 0003 | Also wait for reserved-page USB completion | Built and reviewed; **not hardware-tested** |

Patches 0001 and 0002 adapt upstream work by **Mehmet Fide**, acknowledged
upstream by **Ping-Ke Shih**. Patch 0003 is a local experimental implementation
inspired by **Mohammed Afifi** and **Bitterblue Smith**. Upstream acknowledgments
concern their versions, not these local adaptations. See [AUTHORS.md](AUTHORS.md).

The queue budget allows a burst of 16 frames and refills one token per 100 ms.
Overflow uses ordinary access-category queues; sleeping clients may miss some
broadcast/multicast traffic. This limits admission rate rather than measuring
firmware queue occupancy, so effectiveness depends on firmware drain rate and
AP timing.

## Tested baseline

- RTL8822BU, USB 3, firmware 30.20.0.
- Debian kernel `7.2.8+deb14-amd64`, source package version `7.2.8-1`.
- AP mode: 5 GHz channel 36, 20 MHz, WPA3, protected management frames.
- GCC 16, pahole 1.32; both variants built with `W=1` and BTF.

The temporary queue-only test was October 9, 2026. The human tester subsequently
reported **“It works!”**. Long-duration stability, repeatable sleep/wake,
multi-client behavior, throughput, and fault injection remain unverified.
USB reset accompanied the module switch, so this single test does not isolate
the patches' contribution from the reset. See [docs/TESTING.md](docs/TESTING.md).

## Build

Obtain matching Debian source and headers using authenticated Debian package
tools. [SOURCE.json](SOURCE.json) records baseline source and package hashes.
The helper checks source hashes, copies the driver into a fresh directory,
applies patches with zero fuzz, and builds only `rtw88_usb`.

```sh
python3 scripts/build.py \
  --source /path/to/linux-source-7.2 \
  --kdir /lib/modules/7.2.8+deb14-amd64/build \
  --variant queue-only
```

Requirements: Python 3, `patch`, GNU make, matching compiler and prepared
headers/`Module.symvers`; pahole when module BTF is enabled. With privately
extracted headers, pass their directory through `--kdir` and provide their
tools through `PATH`/`LD_LIBRARY_PATH`. `--prepare-only` skips compilation.
Other source versions are rejected until reviewed and rebased.

The helper installs and loads nothing. Read
[docs/BUILD-AND-ROLLBACK.md](docs/BUILD-AND-ROLLBACK.md) before a temporary load.
The tested setup preserves the stock module on disk; reboot restores it.

## License and reporting

Distributed under **GPL-2.0-only**, using the original driver's GPL option.
Original Realtek copyright and `GPL-2.0 OR BSD-3-Clause` terms remain applicable
to their original portions. See [LICENSE](LICENSE),
[LICENSES/NOTICE.md](LICENSES/NOTICE.md), and [AUTHORS.md](AUTHORS.md).

OpenAI Codex assisted with investigation, adaptation, review, and documentation;
the human authorized changes and tested hardware. Original authors retain their
credit. No upstream endorsement is claimed. Bug reports should include hardware,
kernel/source version, variant, and sanitized evidence. Remove credentials,
account numbers, SSIDs, client identifiers, and private network configuration.
