# PTY + hci_uart Experiment - Quick Start

**Experiment Goal:** Test if using `hci_uart` instead of VHCI resolves the BLE SMP pairing bug.

## What Was Built

1. **pty_stpbt_bridge** - C program that creates a pseudo-terminal and bridges `/dev/stpbt` data through it
2. **PTY_EXPERIMENT.md** - Detailed testing procedures and troubleshooting guide
3. **test_pty_experiment.sh** - Automated test script for quick setup

## Quick Test (Automated)

```bash
# Build the bridge
make pty_stpbt_bridge

# Run automated test (requires root)
sudo ./test_pty_experiment.sh
```

The script will:
- Stop any existing bridges
- Start the PTY bridge
- Attach hci_uart line discipline
- Verify hci0 creation
- Show next steps

## Quick Test (Manual)

### Terminal 1 - PTY Bridge
```bash
./pty_stpbt_bridge
```

### Terminal 2 - Attach Line Discipline & Test
```bash
sudo ldattach -d -s 115200 15 /tmp/bt_pty
hciconfig hci0 up
hcitool lescan
```

### Terminal 3 - Monitor for Errors
```bash
dmesg -w | grep -i smp
```

## Success Criteria

**Success = SMP works:**
- hci0 shows `Bus: UART` (not VIRTUAL)
- BLE pairing completes without errors
- No "SMP security requested but not available" in dmesg

**Failure = Same SMP bug:**
- Same error appears
- Confirms bug is in bluetooth core, not VHCI-specific
- Move to Phase 2: Google Bumble implementation

## Files Created

```
kindle/
├── src/
│   └── pty_stpbt_bridge.c          # PTY bridge implementation
├── pty_stpbt_bridge                 # Compiled binary
├── Makefile                         # Build configuration
├── PTY_EXPERIMENT.md                # Detailed testing guide
├── PTY_EXPERIMENT_SUMMARY.md        # This file
└── test_pty_experiment.sh           # Automated test script
```

## Architecture Comparison

### Current (VHCI):
```
/dev/stpbt -> vhci_stpbt_bridge -> /dev/vhci -> hci0 (VIRTUAL bus)
```

### New Experiment (UART):
```
/dev/stpbt -> pty_stpbt_bridge -> PTY -> hci_uart -> hci0 (UART bus)
```

## Next Steps Based on Results

| Result | Action |
|--------|--------|
| SMP works | Document solution, create systemd service |
| SMP fails | Implement Google Bumble (userspace BLE stack) |
| New error | Research error, gather more diagnostics |

## Time Estimate

- Setup: 5 minutes
- Testing: 15-30 minutes
- Total: ~30-45 minutes

This is a low-effort, low-risk experiment worth trying before moving to the more complex Bumble implementation.

## References

- Full details: PTY_EXPERIMENT.md
- Research background: BLE_SMP_RESEARCH.md
- Original implementation: src/vhci_stpbt_bridge.c
