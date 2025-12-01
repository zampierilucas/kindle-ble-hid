# Failed Experiments Archive

This directory contains code and documentation from approaches that didn't work.

## PTY + hci_uart Approach (Failed)

**Why it failed:** The `hci_uart` driver requires hardware initialization sequences that cannot be provided through a pseudo-terminal. Successfully attached the N_HCI line discipline but the kernel never created the hci0 device.

### Files

**Documentation:**
- `docs/PTY_EXPERIMENT_SUMMARY_FINAL.md` - Complete analysis of why it failed

**Source Code:**
- `src/pty_stpbt_bridge.c` - Basic PTY bridge
- `src/pty_stpbt_bridge_ldisc.c` - PTY bridge with line discipline attachment

### Key Learnings

1. **VHCI is special** - Creates virtual HCI with zero hardware expectations
2. **hci_uart is hardware-oriented** - Requires proper UART initialization
3. **MediaTek needs proprietary setup** - Hardware-specific init that PTY cannot provide
4. **Kernel workarounds won't work** - Cannot bypass MediaTek hardware requirements at kernel level

## Other Failed Experiments

The following source files were attempted for direct BLE connections but failed due to the kernel SMP bug:
- `ble_connect.c` - Direct BLE connection attempts
- `ble_pair_simple.c` - Simple BLE pairing attempts
- `bt_connect.c` - Classic Bluetooth connection (redundant, BlueZ handles this)
- `bt_inquiry.c` - Classic Bluetooth inquiry (redundant)
- `bt_scan.c` - Classic Bluetooth scanning (redundant)

These files were removed entirely as they don't provide reference value - the kernel SMP bug makes them non-functional.

## Complete History

All code, binaries, and documentation from these experiments are preserved in git:

```bash
git checkout pre-cleanup
```

This includes:
- All failed experiment binaries
- Build artifacts and scripts
- Detailed documentation of each failure
- Step-by-step test results
