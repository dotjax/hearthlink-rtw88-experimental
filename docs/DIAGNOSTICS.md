# Read-only health and traffic snapshots

The diagnostic helper reads local sysfs, `ethtool -i`, and accessible kernel
journal messages. It does not request root access, generate traffic, restart
services, or change driver settings.

```sh
python3 scripts/diagnose.py --interface wlan0 --sample-seconds 5 \
  --since '15 minutes ago' --output build/health-before.json
```

Use a real interface name. Omit `--output` to print JSON; a specified output
file is created with mode 0600 and must not already exist. Its parent directory
must exist. Samples are optional and limited to 30 seconds.

Reports include kernel/firmware/driver version, the loaded USB module's GNU
build ID where readable, USB speed/power state, interface byte/error/drop
counters, observed traffic rates, and counts of selected driver-error messages.
Traffic rates describe activity during the sample, not maximum throughput.
Counter resets/disappearance produce unavailable rates rather than negative
values. An interface index change also invalidates the rates. The two counter
reads are not an atomic snapshot.

The helper omits station lists, MAC/IP addresses, SSIDs, USB serials, and raw
journal messages. Kernel error counts cover the rtw88 family plus the selected
USB device, so another rtw88 adapter can contribute messages. Missing journal
access is reported; a zero count never proves absence of faults. This is a
focused diagnostic snapshot, not a comprehensive security audit.

For comparison, take snapshots around the same workload, variant, reset
procedure, and duration. Use an explicit `--since` time at the start of a test
to keep earlier failures out of the count. Keep generated reports outside Git;
the default `build/` directory is ignored.
