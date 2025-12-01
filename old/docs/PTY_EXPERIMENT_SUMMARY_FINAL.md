# PTY + hci_uart Experiment - Final Summary

**Date:** December 1, 2025
**Status:** COMPLETED - FAILED
**Time Invested:** ~4 hours

## Quick Summary

Attempted to bypass kernel SMP bug by using hci_uart driver instead of VHCI. Successfully attached N_HCI line discipline to pseudo-terminal but kernel did not create hci0 device. Experiment failed - hardware initialization requirements cannot be met with PTY approach.

## What Was Built

1. **pty_stpbt_bridge_ldisc.c** - Complete PTY bridge with line discipline attachment (248.2 KB ARM binary)
2. **Docker build system** - Cross-compilation using Alpine Linux ARM
3. **Testing infrastructure** - Automated test scripts and documentation
4. **Bug fixes** - Fixed O_NONBLOCK issue, implemented proper `ioctl(TIOCSETD)`

## Test Results

| Component | Status | Details |
|-----------|--------|---------|
| PTY Creation | ✓ Pass | Created /dev/pts/8 successfully |
| stpbt Access | ✓ Pass | Opened /dev/stpbt (fd=3) |
| Line Discipline | ✓ Pass | N_HCI attached successfully |
| hci0 Creation | ✗ **FAIL** | No HCI device created |
| Data Flow | ✗ FAIL | No packets exchanged |
| SMP Bug Fix | ✗ FAIL | Cannot test without hci0 |

## Why It Failed

The hci_uart driver is designed for real UART hardware and expects:
1. Hardware initialization handshakes
2. Firmware download sequences
3. MediaTek WMT-specific setup
4. Immediate data availability

Our PTY cannot provide these because:
- VHCI bypasses hardware initialization (creates hci0 immediately)
- `/dev/stpbt` won't send data until it receives commands
- Can't send commands without hci0
- Creates unsolvable chicken-and-egg problem

## Key Learnings

1. **VHCI is Special**: Creates virtual HCI with zero hardware expectations
2. **hci_uart is Hardware-Oriented**: Requires proper UART initialization
3. **MediaTek Needs Proprietary Setup**: Hardware-specific initialization that PTY cannot provide
4. **Kernel Workarounds Won't Work**: Cannot bypass MediaTek hardware requirements at kernel level

## Documentation Created

- `PTY_EXPERIMENT_RESULTS.md` - Complete technical analysis
- `PTY_EXPERIMENT.md` - Testing procedures
- `KINDLE_DEPLOYMENT.md` - Deployment guide
- `BLE_SMP_RESEARCH.md` - Updated with failure analysis

## Next Steps

**Proceed with Phase 2: Google Bumble**

Bumble is the correct solution because it:
- Operates entirely in userspace
- Bypasses kernel Bluetooth code (including SMP bugs)
- Can implement MediaTek-specific initialization
- Provides complete BLE stack with SMP support
- Supports BLE HID profiles directly

## Files to Preserve

All experiment files have been preserved for future reference:
```
kindle/
├── src/
│   ├── pty_stpbt_bridge.c
│   └── pty_stpbt_bridge_ldisc.c
├── pty_stpbt_bridge_musl (ARM binary)
├── build_arm_musl.sh
├── PTY_EXPERIMENT*.md
└── KINDLE_DEPLOYMENT.md
```

## Conclusion

The PTY + hci_uart experiment was a valuable learning experience that confirmed:
- Kernel-level workarounds cannot solve this problem
- Google Bumble userspace approach is the correct path forward
- The original research assessment was accurate

**Final Recommendation:** Implement Google Bumble (Phase 2)
