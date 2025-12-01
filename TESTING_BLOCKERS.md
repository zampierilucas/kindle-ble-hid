# Testing Blockers for Bumble BLE HID Solution

**Date:** December 1, 2025
**Status:** BLOCKED - Python version incompatibility

## Problem

The Bumble BLE HID implementation cannot be tested on the Kindle because:

1. **Kindle has no native Python installation**
   - No python/python3 in base system
   - Kindle OS is minimal, optimized for reading

2. **Alpine Linux chroot has Python 3.7.4**
   - Alpine version: 3.11_alpha20190809 (very old)
   - Python 3.7.4 installed
   - pip upgraded to 24.0

3. **Bumble requires Python 3.8+**
   - All Bumble versions (0.0.7 onwards) require Python >=3.8
   - No compatible version available for Python 3.7

## Attempted Solutions

1. **Used Alpine Linux chroot** (`/mnt/us/alpine.ext3`)
   - Successfully mounted and accessed
   - Python 3.7.4 found
   - pip upgraded to 24.0
   - Still incompatible with Bumble

2. **Tried installing old Bumble version**
   - No versions compatible with Python 3.7
   - Earliest version (0.0.7) requires Python 3.8

## Alternative Solutions

### Option 1: Upgrade Alpine Python (RECOMMENDED)

Build Python 3.8+ from source in Alpine:

```bash
# In Alpine chroot
cd /tmp
wget https://www.python.org/ftp/python/3.8.18/Python-3.8.18.tgz
tar xzf Python-3.8.18.tgz
cd Python-3.8.18
./configure --enable-optimizations
make -j4
make altinstall
```

**Pros:**
- Keeps existing Alpine environment
- Python 3.8.18 is stable and compatible
- Can run Bumble BLE HID solution

**Cons:**
- Takes time to compile (~30-60 minutes)
- Requires build tools (may need to add)
- Uses storage space

### Option 2: Create New Alpine Image

Build a fresh Alpine Linux image with Python 3.10+:

```bash
# On development machine
docker run -it --rm alpine:latest
apk add python3 py3-pip
# Export and copy to Kindle
```

**Pros:**
- Clean environment
- Modern Python
- Reproducible

**Cons:**
- Need to recreate entire Alpine setup
- Lose existing Alpine configuration
- Time consuming

### Option 3: PTY + hci_uart Approach (FALLBACK)

Test the PTY-based approach from BLE_SMP_RESEARCH.md Phase 1:

```c
// Create pseudo-TTY wrapper for /dev/stpbt
int master = posix_openpt(O_RDWR);
grantpt(master);
unlockpt(master);
// Bridge stpbt <-> pty
// Use ldattach to attach hci_uart
```

**Pros:**
- No Python dependency
- Uses kernel BT stack (hci_uart)
- Small C program

**Cons:**
- Likely won't fix SMP bug (different code path)
- Need to write C bridge program
- May face same SMP issue

### Option 4: USB Bluetooth Dongle (WORKAROUND)

If Kindle has accessible USB port:

```bash
# Plug in USB BT adapter
# Use standard kernel driver (btusb)
# BlueZ should work normally
```

**Pros:**
- Bypasses all MediaTek/STP issues
- Standard Linux BT stack
- BLE HID should work

**Cons:**
- Requires hardware modification
- May not have accessible USB
- Less elegant solution

### Option 5: Cross-Compile Python 3.8+ for Kindle

Build Python 3.8+ statically linked for ARM:

```bash
# Cross-compile Python with musl
./configure --host=arm-linux-gnueabi \
    --enable-optimizations \
    --with-ensurepip=install
make
# Copy python3.8 binary to Kindle
```

**Pros:**
- Native Kindle execution
- No chroot needed
- Portable

**Cons:**
- Complex cross-compilation
- Need static linking
- Large binary size

## Recommended Path Forward

**SHORT TERM:** Option 1 - Upgrade Python in Alpine

1. Install build dependencies in Alpine (if not present)
2. Compile Python 3.8.18 from source
3. Install as python3.8 (keep 3.7 as fallback)
4. Install Bumble via pip3.8
5. Test BLE HID solution

**Time estimate:** 2-3 hours (mostly compile time)

**LONG TERM:** Option 4 - USB dongle (if testing success)

If Bumble solution proves viable, using USB BT dongle may be more practical for daily use.

## Implementation Attempts

### Attempt 1: Upgrade pip and install Bumble
- Upgraded pip from 19.0.3 to 24.0 in Alpine chroot
- **Result:** FAILED - All Bumble versions require Python 3.8+

### Attempt 2: Install Python 3.11 from Alpine 3.19
- Downloaded python3-3.11.14-r0.apk from Alpine 3.19
- Extracted to Alpine chroot
- **Result:** FAILED - Missing musl libc symbols (time64 functions)
- **Root cause:** Alpine 3.11 has musl 1.1.23, Python 3.11 needs musl 1.2.0+

### Attempt 3: Install Python 3.8 from Alpine 3.11
- Downloaded python3-3.8.10-r0.apk from Alpine 3.11
- Extracted to Alpine chroot
- **Result:** FAILED - Missing `copy_file_range` symbol
- **Root cause:** musl version still too old for Python 3.8.10

## Current Status - DECEMBER 1, 2025 UPDATE (Final)

**BLOCKED - cryptography library cross-compilation infeasible**

- ✅ Python 3.8.18: SUCCESSFULLY CROSS-COMPILED and DEPLOYED
- ✅ zlib module: WORKING (statically linked)
- ✅ All core modules: WORKING (math, asyncio, struct, etc.)
- ✅ Bumble 0.0.200: Pure-Python code installed (downgraded from 0.0.212)
- ✅ Location: /mnt/us/python3.8-kindle/
- ✅ OpenSSL 1.1.1w: SUCCESSFULLY CROSS-COMPILED for ARM (libcrypto.a: 3.6M, libssl.a: 670K)
- ✅ libffi 3.4.4: SUCCESSFULLY CROSS-COMPILED for ARM (static library: 59K)
- ✅ cffi 1.15.1: C extension SUCCESSFULLY CROSS-COMPILED for ARM (_cffi_backend.cpython-38-arm-linux-musleabihf.so)
- ❌ cryptography library: CROSS-COMPILATION BLOCKED - insurmountable cffi version mismatch
- 🚧 Blocker: Cannot build cryptography due to host/target Python version conflicts

### cryptography Cross-Compilation Attempt - Complete Analysis

Successfully cross-compiled dependencies:
1. **OpenSSL 1.1.1w** → `/tmp/openssl-arm/` (3.6M libcrypto.a + 670K libssl.a)
2. **libffi 3.4.4** → `/tmp/libffi-arm/` (59K static library)
3. **cffi 1.15.1 C extension** → ARM shared object compiled successfully

**Fatal blocker encountered:**

The cryptography build system requires running Python scripts (using cffi) on the HOST during cross-compilation to generate C bindings. However:

- Host system: Python 3.13 with cffi 1.17.1 (system RPM, cannot uninstall)
- Target: Python 3.8 with cffi 1.15.1 (cross-compiled ARM)
- cffi version mismatch error: Host's cffi 1.17.1 loads instead of ARM's 1.15.1
- Python 3.13's cffi API incompatible with cffi 1.15.1 source builds
- Cannot isolate cffi versions - Python always loads system version first

Additional complications:
- No Python 3.8 on host system (requires sudo to install)
- cryptography 3.3.2 (last pure cffi version) won't build with mismatched versions
- Newer cryptography versions (35+) require Rust toolchain cross-compilation
- No pre-built ARM wheels available on PyPI for compatible versions
- Alpine chroot has Python 3.7 (too old for Bumble)

**Conclusion:** Cross-compiling cryptography for this specific environment (Python 3.13 host, Python 3.8 ARM target, no sudo access) is not feasible without either:
1. Root access to install Python 3.8 on host
2. Complete rebuild of Alpine chroot with Python 3.8+
3. Using a different development machine with Python 3.8 already installed

### Alternative Solutions Evaluation

1. **Cross-compile cryptography** (FAILED - see above)
   - ✅ OpenSSL cross-compiled
   - ✅ libffi cross-compiled
   - ✅ cffi C extension cross-compiled
   - ❌ cryptography build blocked by cffi version conflicts
   - Status: NOT VIABLE without environment changes

2. **Use Alpine Linux chroot** (BLOCKED)
   - Alpine has pre-built cryptography for ARM
   - But Python 3.7 in Alpine is too old for Bumble (requires 3.8+)
   - Would need to compile Python 3.8+ in Alpine first
   - Status: POSSIBLE but requires Python rebuild in chroot

3. **Find older Bumble without cryptography** (UNLIKELY)
   - All Bumble versions use cryptography for BLE SMP
   - Cannot bypass SMP for BLE HID pairing
   - Status: NOT VIABLE

4. **Kindle-specific toolchains** (EVALUATED - WOULD NOT SOLVE THE PROBLEM)
   - Amazon-Kindle-Cross-Toolchain: Pre-built arm-kindle-linux-gnueabi toolchain
   - kindle-env: OpenEmbedded/Gentoo crossdev environment for Kindle
   - crosstool-NG: Custom toolchain builder (can match exact GCC/glibc)
   - Current toolchain: arm-linux-musleabihf-cross (GCC 11.2.1, musl libc)
   - **Analysis:** The cffi version mismatch is a Python/pip issue, not a toolchain issue
   - Different ARM toolchain won't fix the host Python 3.13 loading system cffi 1.17.1
   - Status: NOT APPLICABLE - toolchain works fine, problem is in Python build system

📝 Next step: Build Python 3.8+ in Alpine chroot or find machine with Python 3.8

## Root Cause Analysis

The Alpine Linux chroot on the Kindle is from 2019 (3.11_alpha) and has:
- musl libc 1.1.23 (released 2019)
- Python 3.7.4

Any Python 3.8+ binary from newer Alpine releases requires:
- musl 1.2.0+ for time64 support
- Linux kernel features like `copy_file_range` (kernel 4.5+)

The Kindle kernel (4.9.77-lab126) has `copy_file_range`, but the musl version is the blocker.

## Viable Options Forward

### Option A: Build Static Python Binary (RECOMMENDED)
Cross-compile Python 3.8+ with static musl linking on development machine:

```bash
# On x86_64 Fedora host
# Install ARM cross-compiler
dnf install gcc-arm-linux-gnu
wget https://musl.cc/arm-linux-musleabihf-cross.tgz
tar -xzf arm-linux-musleabihf-cross.tgz

# Build Python statically
wget https://www.python.org/ftp/python/3.8.18/Python-3.8.18.tgz
tar -xzf Python-3.8.18.tgz
cd Python-3.8.18
./configure \
    --host=arm-linux-musleabihf \
    --build=x86_64-linux-gnu \
    --disable-shared \
    --enable-optimizations \
    LDFLAGS="-static"
make
```

**Time estimate:** 3-4 hours (including cross-compiler setup)

### Option B: PTY + hci_uart (FALLBACK)
Implement the PTY-based approach from BLE_SMP_RESEARCH.md.

**Pros:** No Python needed
**Cons:** May not solve SMP bug

### Option C: USB Bluetooth Dongle (HARDWARE WORKAROUND)
Use external USB Bluetooth adapter.

## Next Steps

Recommend proceeding with Option A (static Python binary) or Option B (PTY approach).

## References

- Bumble PyPI: https://pypi.org/project/bumble/
- Python 3.8.18: https://www.python.org/downloads/release/python-3818/
- Alpine Linux packages: https://pkgs.alpinelinux.org/packages
- BLE_SMP_RESEARCH.md: ../BLE_SMP_RESEARCH.md
