# Cryptography Installation for Kindle

This package contains ARM-compiled Python wheels for the cryptography library and its dependencies.

## Contents

- `cryptography-44.0.3-cp37-abi3-linux_armv7l.whl` - Main cryptography library
- `cffi-2.0.0-cp311-cp311-linux_armv7l.whl` - C Foreign Function Interface (dependency)
- `pycparser-2.23-py3-none-any.whl` - C parser (dependency of cffi)

## Installation Instructions

1. Copy this entire directory to your Kindle device

2. On the Kindle, install the wheels in dependency order:

```bash
# Install pycparser first (no dependencies)
pip3 install --no-index --find-links=. pycparser-2.23-py3-none-any.whl

# Install cffi (depends on pycparser)
pip3 install --no-index --find-links=. cffi-2.0.0-cp311-cp311-linux_armv7l.whl

# Install cryptography (depends on cffi)
pip3 install --no-index --find-links=. cryptography-44.0.3-cp37-abi3-linux_armv7l.whl
```

Or install all at once:

```bash
pip3 install --no-index --find-links=. *.whl
```

## Verification

After installation, verify cryptography is working:

```bash
python3 -c "from cryptography.fernet import Fernet; print('Cryptography installed successfully!')"
```

## Notes

- These wheels were built for ARM architecture (armv7l) with musl libc
- Built using Alpine Linux 3.18 in Docker with QEMU emulation
- Compatible with Python 3.7+ (cryptography uses abi3)
- The cffi wheel is specific to Python 3.11
