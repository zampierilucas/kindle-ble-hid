#!/bin/bash
# Test which buttons are being reported in event2

echo "Monitoring /dev/input/event2 for button events..."
echo "Press buttons on the clicker and watch for events."
echo "Press Ctrl+C to stop."
echo ""

# Use evtest if available, otherwise hexdump
if command -v evtest &> /dev/null; then
    evtest /dev/input/event2
else
    # Decode input events manually
    hexdump -v -e '24/1 "%02x " "\n"' /dev/input/event2 | while read line; do
        # Parse input_event struct: time(16 bytes) + type(2) + code(2) + value(4)
        echo "$line" | awk '{
            type = strtonum("0x" $19 $18)
            code = strtonum("0x" $21 $20)
            value = strtonum("0x" $25 $24 $23 $22)

            if (type == 1) {  # EV_KEY
                key_names[272] = "BTN_LEFT"
                key_names[273] = "BTN_RIGHT"
                key_names[274] = "BTN_MIDDLE"
                key_names[288] = "BTN_GAMEPAD/BTN_1"
                key_names[289] = "BTN_2"
                key_names[290] = "BTN_3"
                key_names[291] = "BTN_4"
                key_names[292] = "BTN_5"
                key_names[293] = "BTN_6"
                key_names[294] = "BTN_7"
                key_names[295] = "BTN_8"

                name = key_names[code]
                if (name == "") name = "UNKNOWN"

                state = (value == 1) ? "PRESS" : "RELEASE"
                printf "EV_KEY: code=%d (%s) value=%d (%s)\n", code, name, value, state
            }
        }'
    done
fi
