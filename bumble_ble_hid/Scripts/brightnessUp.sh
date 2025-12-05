#!/bin/bash

BRIGHTNESS_FILE="/sys/class/backlight/sgm3756/brightness"
MAX_BRIGHTNESS=2010
MIN_BRIGHTNESS=0
MIN_STEP=10

current_brightness=$(cat $BRIGHTNESS_FILE 2>/dev/null)

if [[ ! $current_brightness =~ ^[0-9]+$ ]]; then
    exit 1
fi

# Handle edge case at zero brightness
if [ "$current_brightness" -eq 0 ]; then
    new_brightness=$MIN_STEP
else
    # Adaptive step: ~5% of current brightness (logarithmic curve)
    # Smaller steps at low brightness, larger steps at high brightness
    step_size=$((current_brightness * 5 / 100))

    # Ensure minimum step size
    if [ "$step_size" -lt "$MIN_STEP" ]; then
        step_size=$MIN_STEP
    fi

    new_brightness=$((current_brightness + step_size))
fi

if [ "$new_brightness" -gt "$MAX_BRIGHTNESS" ]; then
    new_brightness=$MAX_BRIGHTNESS
fi

echo $new_brightness > $BRIGHTNESS_FILE
