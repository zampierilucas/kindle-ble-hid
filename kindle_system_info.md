# Kindle System Information

Gathered for cross-compilation and kernel module development.

## Basic System Info

- **Hostname**: kindle
- **Kernel**: Linux 4.9.77-lab126
- **Architecture**: armv7l (ARMv7 32-bit)
- **Build Date**: Tue Aug 1 12:13:39 UTC 2023
- **Compiler Used**: GCC 4.9.1

## Kindle Version

- **System Software**: 002-juno_16020101_cava_bellatrix-409753
- **Kindle Version**: 5.16.2.1.1
- **Platform**: com.lab126.eink.cava.os

## Hardware

- **Device**: MT8110 Bellatrix (MediaTek MT8512)
- **CPU**: ARMv7 Processor rev 4 (Cortex-A53 based, 2 cores)
- **BogoMIPS**: 26.00
- **CPU Features**: half thumb fastmult vfp edsp neon vfpv3 tls vfpv4 idiva idivt vfpd32 lpae evtstrm aes pmull sha1 sha2 crc32
- **Serial**: 9c4ce73e1e1c0ab2
- **RAM**: ~485 MB total

## Cross-Compilation Target

```
Target: arm-linux-gnueabi (EABI5)
ABI: EABI5 (soft-float or softfp VFP)
Minimum kernel: 2.6.32
Word size: 32-bit
Endianness: Little-endian
```

### Recommended GCC flags

```bash
-march=armv7-a -mfpu=neon-vfpv4 -mfloat-abi=softfp -mtune=cortex-a53
```

### Linker Requirements

```
Interpreter: /lib/ld-linux.so.3
```

## C Library (glibc)

- **Version**: glibc 2.20
- **Path**: /lib/libc-2.20.so
- **Dynamic Linker**: /lib/ld-2.20.so (/lib/ld-linux.so.3)

## Loaded Kernel Modules

| Module | Size | Used By |
|--------|------|---------|
| usb_f_ecm | 6400 | 1 |
| g_ether | 2952 | 0 |
| usb_f_rndis | 14944 | 2 g_ether |
| u_ether | 7872 | 3 usb_f_ecm,g_ether,usb_f_rndis |
| wmt_cdev_bt | 17908 | 0 |
| wlan_drv_gen4m | 1776292 | 0 |
| wmt_chrdev_wifi | 11440 | 1 wlan_drv_gen4m |
| wmt_drv | 963016 | 4 wmt_cdev_bt,wlan_drv_gen4m,wmt_chrdev_wifi |
| usb_f_mass_storage | 32216 | 0 |
| libcomposite | 32776 | 4 |
| configfs | 20880 | 5 |
| goodix_core | 54428 | 1 |
| goodix_ts_i2c | 20048 | 1 goodix_core |
| falcon | 31180 | 0 [permanent] |
| hwtcon_v2 | 142808 | 4 |

## Bluetooth Status - WORKING (BlueZ)

### BlueZ Setup (Recommended)

Amazon's BT stack has been disabled in favor of standard BlueZ 5.43. This provides better compatibility with standard Bluetooth tools and protocols.

**IMPORTANT LIMITATION:** BLE HID device pairing (keyboards, mice) does NOT work due to kernel SMP initialization issue. See `BLE_SMP_LIMITATION.md` for full technical details. Classic Bluetooth and non-secure BLE operations work fine.

**Quick Start:**

```bash
/mnt/us/bluetooth/scripts/start_bluez.sh
```

**Manual Setup:**

```bash
# Load kernel modules
modprobe bluetooth hci_uart hci_vhci
insmod /lib/modules/4.9.77-lab126/extra/wmt_cdev_bt.ko

# Start VHCI bridge (creates HCI interface from /dev/stpbt)
/mnt/us/bluetooth/bin/vhci_stpbt_bridge &

# Bring up HCI interface
export LD_LIBRARY_PATH=/mnt/us/bluetooth/libs
/mnt/us/bluetooth/bin/ld-musl-armhf.so.1 /mnt/us/bluetooth/bin/hciconfig hci0 up

# Start bluetoothd
/mnt/us/bluetooth/bin/ld-musl-armhf.so.1 /mnt/us/bluetooth/libexec/bluetooth/bluetoothd &
```

**Pairing a Device:**

```bash
export LD_LIBRARY_PATH=/mnt/us/bluetooth/libs
/mnt/us/bluetooth/bin/ld-musl-armhf.so.1 /mnt/us/bluetooth/bin/bluetoothctl

# In bluetoothctl:
power on
agent on
default-agent
scan on
# Wait for your device to appear, note its MAC address
pair AA:BB:CC:DD:EE:FF
connect AA:BB:CC:DD:EE:FF
```

### Architecture

The Kindle uses a MediaTek MT8512 combo chip with integrated WiFi/BT. Communication happens via:

- **WMT Driver**: `wmt_drv` - Wireless Management Transport core driver
- **BT Character Device**: `wmt_cdev_bt` - Exposes `/dev/stpbt` for BT data
- **STP Protocol**: Serial Transport Protocol multiplexes WiFi/BT/GPS/FM
- **VHCI Bridge**: `vhci_stpbt_bridge` - Bridges `/dev/stpbt` to virtual HCI for BlueZ

### Amazon BT Stack (DISABLED)

Amazon's ACE (Amazon Common Executive) BT stack has been disabled to allow BlueZ to function. The following services are disabled on boot:

- `btmanagerd` - Main ACE BT manager daemon
- `acsbtfd` - ACE BT framework daemon
- `/etc/modprobe.d/blacklist-amz-bt.conf` - Module blacklist (temporarily moved for manual loading)
- `/etc/sysconfig/platform_variables` - Set `btmanagerd=0`
- Upstart configs disabled: btmanagerd.conf, acsbtfd.conf, asr_bt_reboot.conf, asr_bt_userstore.conf

### Device Nodes

| Device | Major:Minor | Purpose |
|--------|-------------|---------|
| /dev/stpbt | 192:0 | STP Bluetooth data channel |
| /dev/btif | 244:0 | BT interface control |
| /dev/stpwmt | 190:0 | STP WMT control |

### Kernel Threads

- `btif_rxd` - BT interface receive daemon
- `mtk_stp_btm` - STP BT manager
- `mtk_stp_psm` - STP power state manager

### Configuration Files

- `/var/local/zbluetooth/bt_stack.conf` - BT stack configuration
- `/var/local/zbluetooth/bt_did.conf` - Device ID configuration
- `/etc/upstart/btmanagerd.conf` - Upstart service config
- `/etc/sysconfig/platform_variables` - Contains `btmanagerd=1`

### BlueZ Tools Available

All BlueZ tools are installed in `/mnt/us/bluetooth/bin/` and `/mnt/us/bluetooth/libexec/bluetooth/`:

- `bluetoothctl` - Interactive Bluetooth control
- `hciconfig` - HCI device configuration
- `hcitool` - HCI tool for device discovery and connections
- `bluetoothd` - Bluetooth daemon (in /mnt/us/libexec/bluetooth/)
- `btmon` - Bluetooth monitor for debugging
- And many more (see /mnt/us/bin/)

### Kernel Modules

Bluetooth modules in `/lib/modules/4.9.77-lab126/`:
- `bluetooth.ko` - Core Bluetooth subsystem
- `hci_uart.ko` - UART HCI driver
- `hci_vhci.ko` - Virtual HCI driver (used by vhci_stpbt_bridge)
- `wmt_cdev_bt.ko` - MediaTek WMT BT character device (in extra/)
- Others: btusb.ko, btbcm.ko, btintel.ko, btrtl.ko, btqca.ko

## Storage Layout

| Partition | Size | Mount Point | Filesystem | Notes |
|-----------|------|-------------|------------|-------|
| mmcblk0p8 | 512MB | / (root) | ext3 | Read-only root |
| mmcblk0p9 | 512MB | /var/local | ext3 | Writable |
| mmcblk0p10 | ~14GB | /mnt/base-us | vfat | User storage |

### Available Space

- Root: 55.9MB free (88% used)
- /var/local: 443.5MB free (4% used)
- User storage: 10.5GB free (21% used)

## Network Interfaces

| Interface | IP | MAC | Notes |
|-----------|-------|-----|-------|
| wlan0 | 192.168.0.65 | 08:c2:24:e1:35:a3 | WiFi (MediaTek) |
| usb0 | ee:19:00:00:00:00 | USB gadget (RNDIS/ECM) |
| tailscale0 | - | - | Tailscale VPN |

## Important Paths

- User writable: `/mnt/us/`, `/var/local/`
- Root filesystem: Read-only (remount with `mount -o remount,rw /`)
- Kernel modules: `/lib/modules/4.9.77-lab126/`

## Key Libraries Available

### System Libraries (/lib/)
- libc-2.20.so (glibc)
- libpthread-2.20.so
- libm-2.20.so
- libdl-2.20.so
- libbluetooth.so.3.19.15
- libdbus-1.so.3.32.4
- libexpat.so.1.10.0
- libffi.so.8.1.4
- libncurses/libcurses

### Graphics Libraries (/usr/lib/)
- libEGL.so
- libGL.so
- libOSMesa.so

## Kernel Configuration Notes

Full kernel config saved to: `kindle_kernel_config.txt`

Key settings:
- `CONFIG_ARM=y`
- `CONFIG_LOCALVERSION="-lab126"`
- `CONFIG_CROSS_COMPILE="aarch64-linux-gnu-"` (note: builds armv7 despite aarch64 prefix)
- `CONFIG_KERNEL_LZO=y`
- `CONFIG_MODULES=y` (loadable module support)
- `CONFIG_SMP=y`
- `CONFIG_PREEMPT=y`

## SSH Access

```bash
ssh root@192.168.0.65
```

## Useful Commands on Device

```bash
# Remount root as read-write
mount -o remount,rw /

# Check module dependencies
modinfo <module_name>

# List all devices
ls /sys/class/

# Check bluetooth device
ls /sys/class/bluetooth/
cat /sys/class/rfkill/*/type
```
