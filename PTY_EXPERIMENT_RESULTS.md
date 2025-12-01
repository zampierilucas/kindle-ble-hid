# PTY + hci_uart Experiment - Results

**Date:** December 1, 2025
**Author:** Lucas Zampieri <lzampier@redhat.com>

## Executive Summary

The PTY + hci_uart experiment was partially successful but did not achieve the goal of creating an hci0 device with UART bus type.

### What Worked

1. **PTY Creation**: Successfully created pseudo-terminal pairs
2. **stpbt Device Access**: Successfully opened `/dev/stpbt` (after fixing O_NONBLOCK issue)
3. **Line Discipline Attachment**: Successfully attached N_HCI (15) line discipline using `ioctl(TIOCSETD)`
4. **Bridge Operation**: Bridge runs without crashes and waits for data

### What Didn't Work

- **No hci0 Device Created**: Despite successful line discipline attachment, the kernel did not create an hci0 HCI device
- **No Data Flow**: No HCI packets flowing between `/dev/stpbt` and the PTY

## Technical Details

### Successful Operations

```
[DEBUG] Opening stpbt device...
Opened /dev/stpbt (fd=3)
[DEBUG] stpbt opened successfully (fd=3)
[DEBUG] Creating PTY...
Created PTY master (fd=4)
PTY slave: /dev/pts/8
Created symlink: /tmp/bt_pty -> /dev/pts/8
[DEBUG] PTY created successfully (master_fd=4, slave=/dev/pts/8)
[DEBUG] Attaching line discipline...

Attaching line discipline...
Opening PTY slave: /dev/pts/8 (fd=5)
Successfully attached N_HCI line discipline (15)
[DEBUG] Line discipline attached successfully (slave_fd=5)

Waiting for hci0 to appear (may take a few seconds)...
[DEBUG] Starting bridge...
```

### Issue Analysis

The hci_uart driver (with N_HCI line discipline) did not create an hci0 device. Possible reasons:

#### 1. Initialization Handshake Missing

The hci_uart driver might require specific initialization sequences or HCI commands before registering the device. With VHCI:
- Opening `/dev/vhci` immediately creates hci0
- The device appears before any data flows

With hci_uart:
- Line discipline attaches successfully
- But hci0 only appears after certain conditions are met
- May need vendor-specific initialization

#### 2. Driver Behavior Differences

**VHCI (working)**:
```
/dev/stpbt -> vhci_bridge -> /dev/vhci -> hci0 (instant)
```

**hci_uart (not working)**:
```
/dev/stpbt -> pty_bridge -> PTY -> N_HCI ldisc -> ??? (no hci0)
```

####  3. MediaTek-Specific Requirements

The MediaTek MT8512 BT hardware might require:
- Specific power-on sequences
- Vendor HCI commands
- WMT (Wireless Management Task) initialization
- Firmware upload before HCI operation

The VHCI approach bypasses these because `/dev/vhci` is purely virtual - it doesn't care about hardware state. The hci_uart approach tries to treat the PTY as real UART hardware, which may trigger different driver code paths expecting hardware initialization.

## Kernel Module Status

```bash
lsmod | grep hci
```

Shows:
- `hci_uart` is loaded (0 users - not active)
- `hci_vhci` was being used by vhci_stpbt_bridge

After attaching N_HCI line discipline, `hci_uart` use count did not increase, suggesting the driver didn't fully initialize.

## Comparison with Working VHCI

**VHCI Bridge Output:**
```
VHCI-stpbt Bridge for Kindle MediaTek BT
hci0:   Type: Primary  Bus: Virtual
        BD Address: 00:00:46:67:61:01  ACL MTU: 1021:6  SCO MTU: 184:1
        DOWN RUNNING
```

**PTY Bridge Output:**
```
[DEBUG] Starting bridge...
(waiting for data, no hci0)
```

## Key Findings

### Bug Fixes Applied

1. **O_NONBLOCK Issue**: Fixed opening `/dev/stpbt` - must open in blocking mode first, then set non-blocking
   - Original: `open(STPBT_DEVICE, O_RDWR | O_NOCTTY | O_NONBLOCK)` ✗
   - Fixed: `open(STPBT_DEVICE, O_RDWR | O_NOCTTY)` then `fcntl(F_SETFL, O_NONBLOCK)` ✓

2. **Line Discipline Attachment**: Successfully implemented using `ioctl(TIOCSETD, N_HCI)`
   - No need for external `ldattach` tool
   - Line discipline attaches but doesn't trigger hci0 creation

### Root Cause Theory

The hci_uart driver likely expects:
1. Real UART hardware with specific characteristics
2. Immediate data availability (firmware download, init packets)
3. Hardware flow control signals
4. Specific baud rate/termios settings

Our PTY provides none of these until `/dev/stpbt` sends data, but `/dev/stpbt` might not send data until it receives initialization commands - creating a chicken-and-egg problem.

## Comparison: VHCI vs hci_uart Architecture

### VHCI Approach (Working)

**Pros:**
- Simple: Opening `/dev/vhci` creates hci0 immediately
- No hardware dependencies
- Works with any data source

**Cons:**
- Creates "Bus: Virtual" device
- Triggers kernel SMP bug (our original problem)

### hci_uart Approach (Not Working)

**Pros:**
- Would create "Bus: UART" device
- Different kernel code path (might avoid SMP bug)

**Cons:**
- Complex initialization requirements
- Expects real UART hardware behavior
- MediaTek hardware may need vendor-specific setup
- No hci0 created without proper handshake

## Experiment Conclusion

**Result:** FAILED - Did not create hci0 device

The PTY + hci_uart approach successfully:
- Attached the line discipline ✓
- Created the bridge infrastructure ✓

But failed to:
- Trigger hci0 device creation ✗
- Establish data flow ✗
- Avoid the original SMP limitation ✗

## Recommendation

Move to **Phase 2: Google Bumble** implementation as originally planned in BLE_SMP_RESEARCH.md.

### Why Bumble is Better

1. **Complete Control**: Userspace BLE stack with full SMP implementation
2. **No Kernel Dependencies**: Bypasses all kernel Bluetooth code
3. **Direct Hardware Access**: Can implement MediaTek-specific initialization
4. **Proven Solution**: Active project with good documentation
5. **Flexibility**: Can implement any BLE profile

## Files Created

```
kindle/
├── src/
│   ├── pty_stpbt_bridge.c           # Simple PTY bridge (no ldisc)
│   └── pty_stpbt_bridge_ldisc.c     # PTY bridge with line discipline
├── pty_stpbt_bridge_musl            # ARM binary (248.2 KB)
├── build_arm_musl.sh                # Docker build script
├── PTY_EXPERIMENT.md                # Testing procedures
├── PTY_EXPERIMENT_SUMMARY.md        # Quick reference
├── PTY_EXPERIMENT_RESULTS.md        # This file
├── KINDLE_DEPLOYMENT.md             # Deployment guide
└── kindle_test_simple.sh            # Test script
```

## Lessons Learned

1. **VHCI is Special**: It's designed for virtual HCI - no hardware expectations
2. **hci_uart is Hardware-Oriented**: Expects real UART with proper initialization
3. **MediaTek is Proprietary**: Likely needs vendor-specific setup that VHCI bypasses
4. **Line Disciplines Work**: We successfully attached N_HCI, proving the mechanism works
5. **PTY Limitations**: PTYs can't fully emulate hardware characteristics

## Next Steps

1. Archive this experiment for reference
2. Begin Google Bumble implementation:
   - Install Python on Kindle (if not present) or cross-compile
   - Create Bumble transport for `/dev/stpbt`
   - Implement BLE HID profile
   - Use `/dev/uhid` for HID device creation
3. Document Bumble approach thoroughly

## References

- BLE_SMP_RESEARCH.md - Original research and Phase 2 plan
- hci_ldisc.c - Kernel HCI UART line discipline driver
- hci_uart.h - UART protocol definitions
- https://github.com/google/bumble - Google Bumble project

---

**Time Invested:** ~4 hours
**Outcome:** Experiment failed, but gained valuable insights
**Next Action:** Proceed with Bumble implementation
