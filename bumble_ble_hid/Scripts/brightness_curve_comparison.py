#!/usr/bin/env python3
"""
Visualize the adaptive brightness curve vs fixed step size
"""

import matplotlib.pyplot as plt
import numpy as np

MAX_BRIGHTNESS = 2010
MIN_STEP = 10
FIXED_STEP = 50

def simulate_brightness_up_adaptive(start, num_presses):
    """Simulate adaptive brightness increases"""
    brightness_values = [start]
    current = start

    for _ in range(num_presses):
        if current == 0:
            step = MIN_STEP
        else:
            step = max(MIN_STEP, int(current * 5 / 100))

        current = min(MAX_BRIGHTNESS, current + step)
        brightness_values.append(current)

    return brightness_values

def simulate_brightness_up_fixed(start, num_presses):
    """Simulate fixed step brightness increases"""
    brightness_values = [start]
    current = start

    for _ in range(num_presses):
        current = min(MAX_BRIGHTNESS, current + FIXED_STEP)
        brightness_values.append(current)

    return brightness_values

def calculate_step_sizes(brightness_values):
    """Calculate step sizes between consecutive brightness values"""
    return [brightness_values[i] - brightness_values[i-1]
            for i in range(1, len(brightness_values))]

# Create figure with two subplots
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

# Simulate from different starting points
starting_points = [10, 100, 500, 1000]
colors = ['blue', 'green', 'orange', 'red']
num_presses = 30

# Plot 1: Brightness progression
for start, color in zip(starting_points, colors):
    adaptive = simulate_brightness_up_adaptive(start, num_presses)
    fixed = simulate_brightness_up_fixed(start, num_presses)

    presses = list(range(len(adaptive)))

    ax1.plot(presses, adaptive, '-o', color=color, label=f'Adaptive (start={start})',
             linewidth=2, markersize=4)
    ax1.plot(presses, fixed, '--s', color=color, alpha=0.5,
             label=f'Fixed (start={start})', linewidth=1, markersize=3)

ax1.set_xlabel('Button Presses', fontsize=12)
ax1.set_ylabel('Brightness Level', fontsize=12)
ax1.set_title('Brightness Progression: Adaptive vs Fixed Step', fontsize=14, fontweight='bold')
ax1.grid(True, alpha=0.3)
ax1.legend(loc='best', fontsize=9)
ax1.set_ylim([0, MAX_BRIGHTNESS * 1.1])

# Plot 2: Step size as function of current brightness
brightness_range = np.linspace(0, MAX_BRIGHTNESS, 100)
adaptive_steps = [max(MIN_STEP, int(b * 5 / 100)) if b > 0 else MIN_STEP
                  for b in brightness_range]
fixed_steps = [FIXED_STEP] * len(brightness_range)

ax2.plot(brightness_range, adaptive_steps, '-', color='blue',
         linewidth=2.5, label='Adaptive (5% of current)')
ax2.plot(brightness_range, fixed_steps, '--', color='red',
         linewidth=2, label=f'Fixed ({FIXED_STEP})')
ax2.axhline(y=MIN_STEP, color='gray', linestyle=':', alpha=0.5,
            label=f'Min step ({MIN_STEP})')

ax2.set_xlabel('Current Brightness Level', fontsize=12)
ax2.set_ylabel('Step Size', fontsize=12)
ax2.set_title('Step Size vs Current Brightness (Logarithmic Curve)',
              fontsize=14, fontweight='bold')
ax2.grid(True, alpha=0.3)
ax2.legend(loc='best', fontsize=10)
ax2.set_ylim([0, 120])

# Add annotation showing the logarithmic nature
ax2.annotate('Small steps at low brightness\n(fine control where eyes are sensitive)',
             xy=(200, 15), xytext=(600, 40),
             arrowprops=dict(arrowstyle='->', color='green', lw=1.5),
             fontsize=10, color='green', fontweight='bold')

ax2.annotate('Large steps at high brightness\n(quick adjustment)',
             xy=(1800, 90), xytext=(1200, 105),
             arrowprops=dict(arrowstyle='->', color='orange', lw=1.5),
             fontsize=10, color='orange', fontweight='bold')

plt.tight_layout()
plt.savefig('/home/lzampier/kindle/bumble_ble_hid/Scripts/brightness_curve.png',
            dpi=150, bbox_inches='tight')
print("Curve visualization saved to: brightness_curve.png")

# Print some example values
print("\nExample step sizes at different brightness levels:")
print("=" * 50)
test_levels = [0, 10, 50, 100, 200, 500, 1000, 1500, 2000]
for level in test_levels:
    if level == 0:
        step = MIN_STEP
    else:
        step = max(MIN_STEP, int(level * 5 / 100))
    print(f"Brightness {level:4d} -> Step size: {step:3d} -> New: {min(MAX_BRIGHTNESS, level + step):4d}")
