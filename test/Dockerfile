FROM python:3.8-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Bumble
RUN pip3 install bumble==0.0.200

# Create test directories
RUN mkdir -p /test /dev/input
WORKDIR /test

# Copy test files
COPY bumble_ble_hid/ /test/bumble_ble_hid/
COPY test/ /test/

# Set environment for pure pass-through mode (default)
ENV KINDLE_BLE_HID_PATCH_DESCRIPTOR=0

CMD ["/bin/bash"]
