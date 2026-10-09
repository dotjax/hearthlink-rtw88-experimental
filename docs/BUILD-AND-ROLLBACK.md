# Build and temporary test

Experimental module changes interrupt Wi-Fi and can crash the host. Use a local
console or wired access, and save work. The build helper accepts only the
baseline in `SOURCE.json`; another version needs review/rebasing.

## Source and headers

Historical Debian packages, all version `7.2.8-1`:

```text
linux-source-7.2
linux-headers-7.2.8+deb14-amd64
linux-headers-7.2.8+deb14-common
linux-kbuild-7.2.8+deb14
```

Download using authenticated Debian package tools and compare package hashes
against `SOURCE.json`. Extract packages with `dpkg-deb -x` and the source archive
with `tar -xf`. Installed matching headers normally supply
`/lib/modules/$(uname -r)/build`.

Privately extracted headers need usable paths. The original experiment set
the architecture header Makefile's common-header and output paths to their
extracted directories. Do not change installed headers for this. GCC 16 and
pahole 1.32 were used; appropriate pahole support is needed for module BTF.

## Build

From the repository root:

```sh
sha256sum -c SHA256SUMS
python3 scripts/build.py --source /path/to/linux-source-7.2 \
  --kdir /lib/modules/7.2.8+deb14-amd64/build --variant queue-only
```

Output: `build/queue-only/source/drivers/net/wireless/realtek/rtw88/rtw88_usb.ko`.
Select a fresh `--output` for another attempt; existing builds are not overwritten.
`--prepare-only` skips compilation. `--variant queue-and-sync` adds the
hardware-untested patch 0003. The helper neither installs nor loads modules.

All 41 driver source/header inputs are checked and only those verified files
are copied, excluding stale objects and source-supplied build files. The
generated kernel release and nonempty `Module.symvers` are checked before any
output is created. These checks do not replace obtaining authenticated matching
header packages. Each output has `build-info.json` with patch, source-manifest,
symbol-table, and resulting module hashes. A failed build remains marked
`compiled: false`.

Inspect `modinfo /absolute/path/to/rtw88_usb.ko`. Vermagic must match the running
kernel, though that alone does not prove safety. Signed-module enforcement may
reject unsigned modules; use your distribution's supported signing procedure
where required.

## Temporary load

Identify the actual chip module, interface, and network manager. These example
commands show the tested **RTL8822BU** unload/load order. Stop the affected AP
or station connection first. Use root authorization permitted by the host:
`sudo -n` fails promptly if these operations are not authorized. Do not execute
over the affected Wi-Fi connection.

```sh
# After stopping the affected connection:
sudo -n modprobe -r rtw88_8822bu
sudo -n modprobe -r rtw88_usb
sudo -n modprobe -a usbcore mac80211 rtw88_core
sudo -n insmod /absolute/path/to/locally-built/rtw88_usb.ko
sudo -n modprobe rtw88_8822bu
# Reactivate the connection with its existing network manager.
```

If any step fails, restore stock modules before continuing. The historical
test also reset the specific wedged USB adapter. Identify the actual device
before any reset; a generic reset script is deliberately not supplied.

The dependency reload is necessary because `modprobe -r` may remove unused
dependencies, while `insmod` does not load them. Verify the locally built
module's dependencies with `modinfo -F depends` if adapting these instructions.
Execute these steps individually and stop on failure; do not blindly paste
the sequence into a shell that continues after errors.

## Rollback

Stop the affected connection, then:

```sh
sudo -n modprobe -r rtw88_8822bu
sudo -n modprobe -r rtw88_usb
sudo -n modprobe rtw88_8822bu
# Reactivate the connection with its existing network manager.
```

`insmod` loads the specified file into memory. With the stock disk module
preserved, `modprobe` uses it again after unloading. Reboot also restores stock
in this temporary setup. Verify that your own system has no separate DKMS,
initramfs, or modprobe override before relying on this. A wedged adapter may
still require targeted reset or power cycling.
