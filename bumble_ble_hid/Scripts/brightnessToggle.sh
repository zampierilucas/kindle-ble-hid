#!/bin/bash

BRIGHTNESS_FILE="/sys/class/backlight/sgm3756/brightness"

MAX_BRIGHTNESS=2010
MIN_BRIGHTNESS=0

current_brightness=$(cat "$BRIGHTNESS_FILE" 2>/dev/null)

if [[ ! $current_brightness =~ ^[0-9]+$ ]]; then
    exit 1
fi

# Calculate midpoint for toggle threshold
MIDPOINT=$(( (MAX_BRIGHTNESS + MIN_BRIGHTNESS) / 50 ))

if [ "$current_brightness" -gt "$MIDPOINT" ]; then
    new_brightness=$MIN_BRIGHTNESS
else
    new_brightness=$MAX_BRIGHTNESS
fi

echo $new_brightness > "$BRIGHTNESS_FILE"

if [[ $? -eq 0 ]]; then
    echo "Brightness toggled to $new_brightness"
else
    echo "Failed to update brightness"
    exit 1
fi

