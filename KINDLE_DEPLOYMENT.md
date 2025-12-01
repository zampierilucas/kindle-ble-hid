# PTY Bridge - Kindle Deployment Guide

## Deployment Options

### Option 1: Transfer Source and Build on Kindle (Recommended for Testing)

```bash
# On development machine
scp src/pty_stpbt_bridge.c root@192.168.0.65:/tmp/

# On Kindle
ssh root@192.168.0.65
cd /tmp
gcc -Wall -O2 -static -o pty_stpbt_bridge pty_stpbt_bridge.c

# If gcc not available, try without static
gcc -Wall -O2 -o pty_stpbt_bridge pty_stpbt_bridge.c
```

### Option 2: Use Pre-built x86 Binary (For Quick Testing Only)

```bash
# Transfer local build (won't work, but for reference)
scp pty_stpbt_bridge root@192.168.0.65:/tmp/
```

### Option 3: Cross-Compile (When Toolchain Available)

```bash
# Build ARM static binary
make arm-static

# Transfer to Kindle
scp pty_stpbt_bridge_arm root@192.168.0.65:/mnt/us/bluetooth/bin/
```

## Quick Test on Kindle

```bash
# SSH to Kindle
ssh root@192.168.0.65

# Stop existing bridges
killall vhci_stpbt_bridge 2>/dev/null || true

# Run PTY bridge
cd /tmp  # or wherever you built it
./pty_stpbt_bridge
```

In another SSH session:

```bash
ssh root@192.168.0.65

# Attach hci_uart
ldattach -d -s 115200 15 /tmp/bt_pty

# Check if hci0 appeared
hciconfig -a

# Power on and test
hciconfig hci0 up
hcitool lescan
```

## Verify Bus Type

The critical test is checking the bus type:

```bash
hciconfig hci0 | grep "Bus:"
```

Should show:
- **UART** (success - different kernel path)
- **VIRTUAL** (means something went wrong)

## Monitor for SMP Errors

```bash
dmesg -w | grep -i smp
```

## Test BLE Pairing

```bash
export LD_LIBRARY_PATH=/mnt/us/bluetooth/libs
/mnt/us/bluetooth/bin/ld-musl-armhf.so.1 /mnt/us/bluetooth/bin/bluetoothctl

[bluetooth]# power on
[bluetooth]# scan on
[bluetooth]# pair XX:XX:XX:XX:XX:XX
```

Watch for "SMP security requested but not available" error.

## Cleanup

```bash
killall ldattach
killall pty_stpbt_bridge
hciconfig hci0 down
```

## Expected File Sizes

```
pty_stpbt_bridge (static):  ~900KB - 1.2MB
pty_stpbt_bridge (dynamic): ~15-20KB
```

## Troubleshooting

### "gcc: command not found"
Kindle doesn't have gcc. You'll need to:
1. Cross-compile from development machine
2. Or install a toolchain on the Kindle (not recommended)

### "/dev/stpbt: Permission denied"
```bash
chmod 666 /dev/stpbt
# or
sudo ./pty_stpbt_bridge
```

### "ldattach: cannot get line discipline"
Check that hci_uart module is loaded:
```bash
lsmod | grep hci_uart
modprobe hci_uart
```
