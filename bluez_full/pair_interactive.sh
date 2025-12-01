#!/bin/bash
# Interactive bluetoothctl pairing script

DEVICE_MAC="5C:2B:3E:50:4F:04"

cd /mnt/us
export LD_LIBRARY_PATH=/mnt/us/libs

# Create a temporary command file
cat > /tmp/bt_commands.txt << 'EOF'
scan on
sleep 10
pair 5C:2B:3E:50:4F:04
sleep 3
trust 5C:2B:3E:50:4F:04
sleep 1
connect 5C:2B:3E:50:4F:04
sleep 2
info 5C:2B:3E:50:4F:04
sleep 1
quit
EOF

# Run bluetoothctl with commands
./ld-musl-armhf.so.1 ./bin/bluetoothctl < /tmp/bt_commands.txt

rm -f /tmp/bt_commands.txt
