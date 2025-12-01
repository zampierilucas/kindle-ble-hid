# PTY Experiment - Ready to Test on Kindle

## What's Ready

1. **pty_stpbt_bridge_musl** - ARM static binary (237KB) - DEPLOYED to Kindle at /tmp/pty_stpbt_bridge
2. **kindle_test.sh** - Automated test script - DEPLOYED to Kindle at /tmp/kindle_test.sh
3. **Complete documentation** - Testing procedures and troubleshooting

## Quick Start - Run on Kindle

SSH to the Kindle and run:

```bash
ssh root@192.168.0.65
cd /tmp
bash kindle_test.sh
```

This automated script will:
1. Stop the existing vhci_stpbt_bridge
2. Start the new PTY bridge
3. Attach hci_uart line discipline
4. Verify hci0 creation
5. Check bus type (should be UART, not VIRTUAL)

## Expected Output

```
=== PTY + hci_uart Experiment on Kindle ===

[1] Stopping existing vhci bridge...
[2] Checking prerequisites...
Prerequisites OK

[3] Starting PTY bridge...
Bridge PID: XXXX
PTY created: /tmp/bt_pty

[4] Attaching hci_uart (N_HCI=15)...
[5] Checking hci0...

SUCCESS: hci0 created!

Bus type: UART

SUCCESS: Using UART bus (experiment working!)
```

## Next Steps After Setup

Once the script completes successfully:

### 1. Power On and Scan

```bash
hciconfig hci0 up
hcitool lescan
```

### 2. Test BLE Pairing

```bash
export LD_LIBRARY_PATH=/mnt/us/bluetooth/libs
/mnt/us/bluetooth/bin/ld-musl-armhf.so.1 /mnt/us/bluetooth/bin/bluetoothctl

[bluetooth]# power on
[bluetooth]# scan on
[bluetooth]# pair XX:XX:XX:XX:XX:XX  # Your BLE HID device
```

### 3. Monitor for SMP Errors

In another SSH session:

```bash
dmesg -w | grep -i smp
```

**Look for:** "SMP security requested but not available"
- **If this appears:** Experiment failed, SMP bug is in bluetooth core
- **If it doesn't appear:** SUCCESS! UART path avoids the bug

## Critical Test

The key indicator is the bus type:

```bash
hciconfig hci0 | grep "Bus:"
```

- **UART** = Good! Different kernel path than VHCI
- **VIRTUAL** = Problem, something went wrong

## Cleanup

```bash
killall ldattach
killall pty_stpbt_bridge
```

## What Was Built

### Build Process

Used Docker with Alpine Linux ARM (arm32v7/alpine:3.19) to cross-compile:

```bash
./build_arm_musl.sh  # Builds pty_stpbt_bridge_musl
```

### Binary Details

```
File: pty_stpbt_bridge_musl
Type: ELF 32-bit LSB ARM EABI5
Link: Statically linked (musl libc)
Size: 237.6 KB
Arch: ARMv7-A, Cortex-A53 optimized
```

### Files Created

```
kindle/
├── src/pty_stpbt_bridge.c           # Source code
├── pty_stpbt_bridge_musl            # ARM binary (ready)
├── build_arm_musl.sh                # Docker build script
├── kindle_test.sh                   # Automated test (on Kindle)
├── KINDLE_DEPLOYMENT.md             # Deployment guide
├── PTY_EXPERIMENT.md                # Detailed testing procedures
├── PTY_EXPERIMENT_SUMMARY.md        # Quick reference
└── READY_TO_TEST.md                 # This file
```

### On Kindle

```
/tmp/pty_stpbt_bridge                # Binary (deployed)
/tmp/kindle_test.sh                  # Test script (deployed)
/tmp/pty_stpbt_bridge.c              # Source (optional)
```

## Success/Failure Criteria

### Success (UART Path Works)

- Bus shows "UART"
- BLE devices pair successfully
- No SMP errors in dmesg
- **Action:** Document solution, move to production
- **Conclusion:** VHCI-specific SMP bug confirmed

### Failure (SMP Bug Persists)

- Same "SMP security requested but not available"
- **Action:** Move to Phase 2 - Google Bumble
- **Conclusion:** Bug is in bluetooth core, not transport-specific

## Troubleshooting

### "Resource busy" on /dev/stpbt

```bash
killall vhci_stpbt_bridge
killall pty_stpbt_bridge
lsof /dev/stpbt
```

### hci0 doesn't appear

```bash
lsmod | grep hci_uart
modprobe hci_uart
dmesg | tail -20
```

### PTY not created

Check bridge output:
```bash
/tmp/pty_stpbt_bridge
# Should create /tmp/bt_pty
```

## Time Estimate

- Setup: 2-3 minutes
- Testing: 10-15 minutes
- Total: ~15-20 minutes

## References

- Source: src/pty_stpbt_bridge.c:1
- Research: BLE_SMP_RESEARCH.md (Phase 1)
- Original: src/vhci_stpbt_bridge.c

## Author

Lucas Zampieri <lzampier@redhat.com>
December 1, 2025
