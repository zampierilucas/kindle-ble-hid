# BLE HID Script Mode

This version of the Kindle BLE HID implementation executes shell scripts in response to button presses instead of injecting events into the Linux kernel via UHID.

## What Changed

### Removed
- UHID device creation and kernel integration
- All HID descriptor generation code (permissive, standard keyboard/mouse)
- Environment variables: `KINDLE_BLE_HID_DESCRIPTOR_MODE`, `KINDLE_BLE_HID_USE_ORIGINAL_DESCRIPTOR`

### Added
- `ButtonScriptExecutor` class for script execution
- Configurable button-to-script mapping via JSON
- Background script execution using `subprocess.Popen`

## Configuration

Button mappings are configured in `/mnt/us/bumble_ble_hid/button_config.json`:

```json
{
  "buttons": {
    "0x01": "/mnt/us/PageTurnerLocal/prev.sh",
    "0x02": "/mnt/us/PageTurnerLocal/brightnessUp.sh",
    "0x04": "/mnt/us/PageTurnerLocal/next.sh",
    "0x08": "/mnt/us/PageTurnerLocal/brightnessDown.sh",
    "0x10": "/mnt/us/PageTurnerLocal/tapBar.sh",
    "0x20": "/mnt/us/PageTurnerLocal/tapBar.sh"
  },
  "debounce_ms": 500,
  "log_button_presses": true
}
```

### Button Codes

Based on BLE-M3 device mapping:
- `0x01` - Button 1 (Left)
- `0x02` - Button 2 (Up)
- `0x04` - Button 3 (Right)
- `0x08` - Button 4 (Down)
- `0x10` - Button 5 (Center/Select)
- `0x20` - Button 6 (Enter/Confirm)

### Configuration Options

- `buttons`: Map of button codes (hex string) to script paths
- `debounce_ms`: Milliseconds to wait between button presses (default: 500)
- `log_button_presses`: Whether to log button events (default: true)

## Usage

Start the daemon with button mapping enabled:

```bash
KINDLE_BLE_HID_PATCH_DESCRIPTOR=1 \
  /mnt/us/python3.8-kindle/python3-wrapper.sh \
  /mnt/us/bumble_ble_hid/kindle_ble_hid.py
```

The `KINDLE_BLE_HID_PATCH_DESCRIPTOR=1` environment variable enables the BLE-M3 button mapping logic that translates raw HID reports into clean button codes.

## How It Works

1. BLE device sends HID report (e.g., `0296008601`)
2. `_map_button_combination()` translates report to button code (e.g., `0x01`)
3. `ButtonScriptExecutor.execute_button_script()` looks up script in config
4. Script is launched in background using `subprocess.Popen`
5. Debouncing prevents rapid repeated executions

## Script Requirements

Scripts should be:
- Executable (`chmod +x`)
- Fast-executing or self-daemonizing
- Error-tolerant (script failures won't crash the daemon)

Example script:

```bash
#!/bin/sh
# /mnt/us/PageTurnerLocal/next.sh
echo "Next page" >> /tmp/button.log
# Add your page-turning logic here
```

## Troubleshooting

### Button presses not executing scripts
1. Check config file exists: `/mnt/us/bumble_ble_hid/button_config.json`
2. Verify script paths are correct and executable
3. Check logs for "No script configured" or "Script not found" messages

### Scripts not found
Ensure scripts exist at the configured paths:
```bash
ls -la /mnt/us/PageTurnerLocal/*.sh
```

### Button detection issues
- Verify `KINDLE_BLE_HID_PATCH_DESCRIPTOR=1` is set
- Check logs for "Detected: Button X" messages
- Raw HID reports are logged as "HID Report: ..."

## Migration from UHID Mode

If upgrading from the UHID version:
1. The daemon will automatically use script mode (no UHID device created)
2. Update button_config.json with your desired script paths
3. Remove any UHID-related configuration/workarounds

## Benefits

- Simpler than kernel integration
- No descriptor mismatches
- Easy to customize button actions
- Scripts can trigger any Kindle functionality
- No need for `/dev/uhid` permissions
