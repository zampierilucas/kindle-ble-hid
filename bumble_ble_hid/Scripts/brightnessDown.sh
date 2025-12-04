#!/bin/bash

BRIGHTNESS_FILE="/sys/class/backlight/sgm3756/brightness"
MAX_BRIGHTNESS=2010
MIN_BRIGHTNESS=0
STEPS=10

current_brightness=$(cat $BRIGHTNESS_FILE 2>/dev/null)

if [[ ! $current_brightness =~ ^[0-9]+$ ]]; then
    exit 1
fi

step_size=$(( (MAX_BRIGHTNESS - MIN_BRIGHTNESS) / STEPS ))
new_brightness=$((current_brightness - step_size))

if [ "$new_brightness" -lt "$MIN_BRIGHTNESS" ]; then
    new_brightness=$MIN_BRIGHTNESS
fi

echo $new_brightness > $BRIGHTNESS_FILE
