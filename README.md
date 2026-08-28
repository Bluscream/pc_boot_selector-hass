# PC Boot Selector for Home Assistant

A custom Home Assistant integration to select target operating systems, control BIOS/UEFI boot priority (`BootNext` & `BootOrder`), and adjust boot timeouts directly from your dashboard.

Whenever you change the selection, boot mode, or timeout, configuration files are generated and served via Home Assistant's local HTTP server under `/config/www/boot/{pc_slug}/`.

---

## 🌐 Generated Endpoints & Files

All generated configurations and client tools are exposed publicly on your local network:

| File | Endpoint URL (`homeassistant.local` / `<ha-ip>`) | Description |
| :--- | :--- | :--- |
| **Directory Index** | `http://homeassistant.local:8123/local/boot/<pc-slug>/` | Web UI overview with file links and 1-line installer |
| **`os.txt`** | `http://homeassistant.local:8123/local/boot/<pc-slug>/os.txt` | Plain-text name of active target OS (e.g. `Windows`, `Bazzite`) |
| **`grub.cfg`** | `http://homeassistant.local:8123/local/boot/<pc-slug>/grub.cfg` | GRUB configuration snippet (`set default="..."`, `set timeout=...`) |
| **`limine.conf`** | `http://homeassistant.local:8123/local/boot/<pc-slug>/limine.conf` | Complete multi-boot configuration for Limine bootloader |
| **`bios.conf`** | `http://homeassistant.local:8123/local/boot/<pc-slug>/bios.conf` | BIOS NVRAM parameters (`BOOT_ORDER="..."`, `BOOT_NEXT="..."`) |
| **`update_boot_selector.sh`** | `http://homeassistant.local:8123/local/boot/<pc-slug>/update_boot_selector.sh` | Client sync, extractor, and systemd install script |

---

## 🚀 Features

- 🖥️ **Multi-Bootloader Support:** Synchronizes **GRUB**, **Limine**, and **BIOS / UEFI NVRAM** targets across multiple drives and ESPs.
- ⚡ **BIOS Boot Mode Selection:** Toggle between **One-Time Boot (`BootNext`)** and **Persistent Boot Order (`BootOrder`)**.
- 🔄 **Dual Boot Sync:**
  - **Shutdown Hook:** Pre-sets BIOS `BootNext` and GRUB environment before the OS reboots.
  - **UEFI Network Fallback:** GRUB queries Home Assistant live over HTTP during boot if changes were made while the machine was powered off.
- 🛠️ **Built-in Info Extractor:** Run `update_boot_selector.sh --info` to automatically detect your system's EFI boot numbers, GRUB IDs, and Limine blocks.
- 🛡️ **Network Resilient:** Built-in connection retries and graceful offline fallbacks.

---

## 📦 Installation

### Via HACS (Recommended)
1. Open **HACS** in Home Assistant.
2. Top-right menu ➔ **Custom repositories**.
3. Add `https://github.com/Bluscream/pc_boot_selector-hass` as an **Integration**.
4. Search for **PC Boot Selector** and click **Download**.
5. Restart Home Assistant.

### Manual Installation
Copy `custom_components/pc_boot_selector/` into your Home Assistant `/config/custom_components/` directory and restart.

---

## ⚙️ Configuration

1. In Home Assistant: **Settings** ➔ **Devices & Services** ➔ **Add Integration** ➔ **PC Boot Selector**.
2. **Basic Settings:**
   - **PC Name:** Friendly device name (e.g. `Gaming PC`).
   - **Output Directory:** Output path (default: `/config/www/boot/{slug}/`).
   - **Timeout:** Default boot timeout in seconds.
3. **Add Boot Entries:**
   - **OS Name:** Friendly name (e.g. `Bazzite`, `Windows`, `CachyOS`).
   - **GRUB Entry ID:** GRUB menu ID / title (e.g. `Bazzite (ostree:0)` or `osprober-efi-7C59-B0E8`).
   - **EFI Boot Number:** 4-digit BIOS boot number from `efibootmgr` (e.g. `0002` for `Boot0002`).
   - **Limine Entry Config:** *(Optional)* Multi-line Limine boot entry snippet.

---

## 💡 Extracting Client Configs

Run the client script with `--info` to display all parameters ready for copy-pasting:

```bash
/usr/local/bin/update_boot_selector.sh --info
```

### Sample Output:
```text
---------------------- [ Windows ] ----------------------
Operating System Name (os_name)      : Windows
GRUB Entry ID / Name (grub_id)       : osprober-efi-7C59-B0E8
EFI Boot Number (efi_boot_num)       : 0006

---------------------- [ Bazzite (ostree:0) ] ----------------------
Operating System Name (os_name)      : Bazzite (ostree:0)
GRUB Entry ID / Name (grub_id)       : Bazzite (ostree:0)
EFI Boot Number (efi_boot_num)       : 0002
```

---

## 🖥️ Client PC Setup

### ⚡ 1-Line Automated Service Install:
Run the following command on your client machine to install the automated systemd startup & shutdown sync service:

```bash
wget -O /tmp/update_boot_selector.sh http://homeassistant.local:8123/local/boot/<pc-slug>/update_boot_selector.sh && sudo bash /tmp/update_boot_selector.sh --install
```

### Script CLI Options:
```bash
# Fetch and apply current boot selection (uses /etc/pc-boot-selector.conf)
sudo /usr/local/bin/update_boot_selector.sh

# Force persistent boot mode (grub2-set-default & BootOrder)
sudo /usr/local/bin/update_boot_selector.sh --always

# Extract copy/paste values for Home Assistant setup
/usr/local/bin/update_boot_selector.sh --info

# Override Home Assistant URL or PC slug on demand
sudo /usr/local/bin/update_boot_selector.sh -u http://192.168.2.4:8123 -s gaming-pc
```
