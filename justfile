# Justfile for Kindle BLE HID project
# Usage: just <recipe>

# Default recipe (list all recipes)
default:
    @just --list

# Deploy to Kindle over SSH
deploy:
    @echo "Deploying to Kindle..."
    @echo "Stopping daemon..."
    -ssh kindle "/etc/init.d/ble-hid stop" 2>/dev/null || true
    @echo "Remounting filesystems as writable..."
    ssh kindle "/usr/sbin/mntroot rw && mount -o remount,rw /mnt/base-us"
    @echo "Copying files..."
    scp bumble_ble_hid/*.py kindle:/mnt/us/bumble_ble_hid/
    scp bumble_ble_hid/ble-hid.init kindle:/etc/init.d/ble-hid
    ssh kindle "chmod +x /etc/init.d/ble-hid"
    @echo "Clearing Python bytecode cache..."
    ssh kindle "rm -rf /mnt/us/bumble_ble_hid/__pycache__"
    @echo "Creating cache directory..."
    ssh kindle "mkdir -p /mnt/us/bumble_ble_hid/cache"
    @echo "Starting daemon..."
    ssh kindle "/etc/init.d/ble-hid start"
    @echo "Deployment complete!"
    @echo ""
    @echo "Check status with: just status"
    @echo "View logs with: just logs"

# Check daemon status on Kindle
status:
    @echo "Checking daemon status..."
    ssh kindle "/etc/init.d/ble-hid status"

# View daemon logs
logs:
    @echo "Showing daemon logs (Ctrl+C to exit)..."
    ssh kindle "tail -f /var/log/ble_hid_daemon.log"

# View recent daemon logs
logs-recent:
    @echo "Last 50 lines of daemon log:"
    ssh kindle "tail -n 50 /var/log/ble_hid_daemon.log"

# Restart daemon on Kindle
restart:
    @echo "Restarting daemon..."
    ssh kindle "/etc/init.d/ble-hid restart"
    @echo "Daemon restarted!"

# Stop daemon on Kindle
stop:
    @echo "Stopping daemon..."
    ssh kindle "/etc/init.d/ble-hid stop"
    @echo "Daemon stopped!"

# Start daemon on Kindle
start:
    @echo "Starting daemon..."
    ssh kindle "/etc/init.d/ble-hid start"
    @echo "Daemon started!"

# Clear GATT cache on Kindle
clear-cache:
    @echo "Clearing GATT cache..."
    ssh kindle "rm -rf /mnt/us/bumble_ble_hid/cache/*"
    @echo "Cache cleared! Will regenerate on next connection."

# Show cache contents
show-cache:
    @echo "GATT cache contents:"
    ssh kindle "ls -lh /mnt/us/bumble_ble_hid/cache/ 2>/dev/null || echo 'Cache is empty'"

# SSH into Kindle
ssh:
    ssh kindle

# Run tests locally
test:
    @echo "Running logic-only tests..."
    python3 test/test_logic_only.py

# Check Python syntax
check:
    @echo "Checking Python syntax..."
    python3 -m py_compile bumble_ble_hid/*.py
    @echo "All files compile successfully!"

# Deploy and follow logs
deploy-watch: deploy
    @echo ""
    @echo "Following daemon logs (Ctrl+C to exit)..."
    @just logs
