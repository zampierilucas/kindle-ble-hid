# Logitech Clicker Button Mapping

## Physical Buttons → Clean Button Codes

| Physical Button | Raw Pattern | Clean Code | Bit Position |
|----------------|-------------|------------|--------------|
| LEFT           | 0x96        | 0x01       | Bit 0        |
| UP             | 0x68 (x=0)  | 0x02       | Bit 1        |
| RIGHT          | 0x68 (x≠0)  | 0x04       | Bit 2        |
| DOWN           | 0x68 (y>0)  | 0x08       | Bit 3        |
| CENTER/SELECT  | 0x2c        | 0x10       | Bit 4        |
| ENTER/CONFIRM  | 0xd5        | 0x20       | Bit 5        |

## Expected evdev Button Codes

Based on Mouse HID descriptor (16-button mouse):

| Physical Button | Clean Code | evdev Code | evdev Name    | Decimal |
|----------------|------------|------------|---------------|---------|
| LEFT           | 0x01       | BTN_LEFT   | BTN_MOUSE     | 272     |
| UP             | 0x02       | BTN_RIGHT  | BTN_RIGHT     | 273     |
| RIGHT          | 0x04       | BTN_MIDDLE | BTN_MIDDLE    | 274     |
| DOWN           | 0x08       | BTN_SIDE   | BTN_SIDE      | 275     |
| CENTER/SELECT  | 0x10       | BTN_EXTRA  | BTN_EXTRA     | 276     |
| ENTER/CONFIRM  | 0x20       | BTN_FORWARD| BTN_FORWARD   | 277     |

## Verification

Run `evtest /dev/input/event2` and press each button to confirm the actual evdev codes.

## Usage with evdev Tools

### Using evtest
```bash
evtest /dev/input/event2
# Press each button and note the code number
```

### Using input-event or similar
The button codes can be remapped using tools like:
- `evdev` remapping
- `xmodmap` (if running X11)
- `libinput` configuration
- Custom scripts reading from `/dev/input/event2`

## Raw Report Format

The device sends 5-byte reports:
- Byte 0: Report ID (0x00 or 0x07)
- Byte 1: Button state (bitmap with weird combinations)
- Byte 2: X movement (signed)
- Byte 3: Y movement (signed)
- Byte 4: Wheel (unused)

Our daemon maps the messy button combinations to clean single-bit codes before sending to the kernel.
