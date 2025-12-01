# PTY + hci_uart Experiment

**Date:** December 1, 2025
**Author:** Lucas Zampieri <lzampier@redhat.com>

## Overview

This experiment tests whether using `hci_uart` via a pseudo-terminal instead of the current VHCI approach helps resolve the BLE SMP pairing issue.

## Theory

The current `vhci_stpbt_bridge` uses `/dev/vhci` which creates a virtual HCI device. The kernel may have SMP initialization timing issues specific to virtual devices (`HCI_VIRTUAL` bus type).

By wrapping `/dev/stpbt` in a PTY and using `hci_uart` with the H4 line discipline (N_HCI=15), we force the kernel to use the UART code path instead. This may trigger different SMP initialization logic.

## Architecture

```
MediaTek MT8512 CONSYS
        |
        v
  /dev/stpbt (H4 HCI packets)
        |
        v
  pty_stpbt_bridge (userspace)
        |
        v
  PTY master | PTY slave (/tmp/bt_pty)
        |
        v
  ldattach (N_HCI line discipline)
        |
        v
  hci_uart driver
        |
        v
  Linux Bluetooth (BlueZ)
        |
        v
  hci0 (UART-attached adapter)
```

## Prerequisites

1. Stop any existing Bluetooth bridges:
   ```bash
   killall vhci_stpbt_bridge
   killall pty_stpbt_bridge
   ```

2. Verify hci_uart module is loaded:
   ```bash
   lsmod | grep hci_uart
   ```

3. Verify ldattach is available:
   ```bash
   which ldattach
   ```

## Testing Steps

### Step 1: Start PTY Bridge

```bash
./pty_stpbt_bridge
```

Expected output:
```
PTY-based STP Bluetooth Bridge
================================

Opened /dev/stpbt (fd=3)
Created PTY master (fd=4)
PTY slave: /dev/pts/X
Created symlink: /tmp/bt_pty -> /dev/pts/X

To attach hci_uart line discipline, run:
  ldattach -d -s 115200 15 /tmp/bt_pty

Bridge active. Waiting for data...
Press Ctrl+C to stop.
```

**Keep this terminal open.**

### Step 2: Attach hci_uart Line Discipline

In a second terminal:

```bash
sudo ldattach -d -s 115200 15 /tmp/bt_pty
```

Options explained:
- `-d`: Run in background (daemon mode)
- `-s 115200`: Baud rate (symbolic, PTY doesn't enforce this)
- `15`: Line discipline number (N_HCI)
- `/tmp/bt_pty`: PTY slave device

Expected: Command returns immediately, ldattach runs in background.

### Step 3: Verify HCI Interface

Check if hci0 appeared:

```bash
hciconfig -a
```

Expected output:
```
hci0:   Type: Primary  Bus: UART
        BD Address: XX:XX:XX:XX:XX:XX  ACL MTU: 1021:8  SCO MTU: 255:16
        UP RUNNING
        ...
```

Key: `Bus: UART` (not `Bus: VIRTUAL`)

### Step 4: Check dmesg

```bash
dmesg | tail -20
```

Look for:
```
Bluetooth: HCI UART driver ver X.X
Bluetooth: HCI UART protocol H:4 registered
Bluetooth: HCIDEV (hci0): HCI Enhanced Setup Synchronous Connection command is advertised, but not supported.
```

### Step 5: Power On and Scan

```bash
sudo hciconfig hci0 up
sudo hcitool lescan
```

Watch the first terminal (pty_stpbt_bridge) for data transfer logs:
```
stpbt -> pty: 7 bytes
pty -> stpbt: 4 bytes
...
```

### Step 6: Test BLE Pairing

Try pairing with a BLE HID device:

```bash
bluetoothctl
[bluetooth]# power on
[bluetooth]# scan on
[bluetooth]# pair XX:XX:XX:XX:XX:XX  # Your device address
```

**Check dmesg during pairing:**

```bash
dmesg -w
```

**Success criteria:**
- No "SMP security requested but not available" error
- Pairing completes successfully

**Failure criteria:**
- Same SMP error appears
- Means the bug is in bluetooth core, not VHCI-specific

## Data Collection

Record the following for analysis:

1. **hciconfig output:**
   ```bash
   hciconfig -a > hciconfig_uart.txt
   ```

2. **dmesg output:**
   ```bash
   dmesg > dmesg_uart.txt
   ```

3. **Loaded modules:**
   ```bash
   lsmod > lsmod_uart.txt
   ```

4. **hci0 details:**
   ```bash
   hciconfig hci0 features > features_uart.txt
   ```

## Cleanup

1. Kill ldattach:
   ```bash
   sudo killall ldattach
   ```

2. Stop PTY bridge (Ctrl+C in first terminal)

3. Verify cleanup:
   ```bash
   hciconfig
   ls /tmp/bt_pty  # Should not exist
   ```

## Expected Outcomes

### Best Case: SMP Works
- Pairing succeeds
- No SMP errors in dmesg
- **Action:** Document the solution, create startup scripts
- **Conclusion:** VHCI-specific bug confirmed

### Most Likely: SMP Still Fails
- Same "SMP security requested but not available" error
- **Action:** Move to Phase 2 (Google Bumble implementation)
- **Conclusion:** Bug is in bluetooth core, not transport-specific

### Unexpected: Different Error
- New error messages
- **Action:** Research new error, may reveal additional clues

## Troubleshooting

### ldattach fails with "Device or resource busy"
```bash
# Check what's using the PTY
lsof /tmp/bt_pty

# Force detach previous line discipline
sudo ldattach -d 0 /tmp/bt_pty  # N_TTY (default)
```

### No data transfer shown in bridge
```bash
# Check /dev/stpbt permissions
ls -l /dev/stpbt

# Verify stpbt is open
lsof /dev/stpbt

# Check if MediaTek CONSYS is powered
dmesg | grep -i consys
```

### hci0 doesn't appear
```bash
# Check hci_uart is loaded
lsmod | grep hci_uart

# Try manual hciattach (alternative to ldattach)
sudo hciattach -n /tmp/bt_pty any 115200 noflow
```

## References

- hci_ldisc.c: Line discipline driver for HCI UART
- ldattach(8): Attach line discipline to serial line
- hciattach(1): Attach serial devices to HCI UART driver

## Next Steps

Based on results:
1. If successful: Document, create systemd service
2. If failed: Proceed with Google Bumble implementation (BLE_SMP_RESEARCH.md Phase 2)
