# Attribution and provenance

## Original driver

Linux `rtw88`, developed by Realtek and the Linux wireless community.
Baseline `usb.c` and `usb.h` carry `GPL-2.0 OR BSD-3-Clause` and
`Copyright(c) 2018-2019 Realtek Corporation`.
This repository publishes patches rather than a vendored driver. Obtain the
original source and notices from Debian `linux-source-7.2`, version `7.2.8-1`.
[SOURCE.json](SOURCE.json) identifies the exact baseline.

## Patch 0001

Author: **Mehmet Fide**. Source:
[upstream v3 after-DTIM routing patch](https://patchew.org/linux/20260814053426.2473247-1-mehmet.fide@gmail.com/),
message ID `20260814053426.2473247-1-mehmet.fide@gmail.com`.
The code matches the upstream diff; local explanation and packaging differ.
**Ping-Ke Shih** acknowledged the upstream version, not this repository's tests.

## Patch 0002

Author: **Mehmet Fide**. Source:
[upstream v3 queue-budget patch](https://lists.openwall.net/linux-kernel/2026/09/10/873),
message ID `20260910081716.769081-2-mehmet.fide@gmail.com`.
Algorithm/constants are from that work. Local differences are context offsets,
shorter comments, and whitespace; this is not a new queue-control design.
**Ping-Ke Shih** acknowledged the upstream version. The local set includes
that budget patch rather than the entire upstream three-patch series, so
patch numbering differs.

## Patch 0003

Local experimental implementation developed with Codex assistance, inspired by
**Mohammed Afifi** and **Bitterblue Smith** in
[lwfinger/rtw88 PR 455](https://github.com/lwfinger/rtw88/pull/455).
Reviewed source:
[September reserved-page patch attachment](https://github.com/user-attachments/files/32004196/0001-wifi-rtw88-usb-Download-the-reserved-page-synchronou.patch).

The local implementation retains URB ownership, preserves `URB_ZERO_PACKET`,
propagates transfer/short-write errors, and drains completion with
`usb_kill_urb()` before releasing stack context or packet storage. Only the
beacon/reserved-page path waits. This is not a verbatim upstream patch and
has no upstream acknowledgment or hardware result.

## Local project

**dotjax / Hearthlink** hosts the experiments and supplied human direction and
hardware testing. **OpenAI Codex** assisted with investigation, adaptation,
the local completion implementation, validation, and documentation.
Original driver and upstream patch authors retain their credit. No new
`Signed-off-by` or `Acked-by` trailers have been invented for these adaptations.
