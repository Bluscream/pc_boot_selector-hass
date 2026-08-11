# PC Boot Selector for Home Assistant

A custom Home Assistant integration that enables selecting operating systems, setting BIOS boot order / one-time boot options (`BootNext`), and adjusting boot timeouts for PCs directly from your Home Assistant dashboard.

Whenever you change the selection, boot mode, or timeout in Home Assistant, the integration writes:
- `os.txt` (Friendly name of the target OS, e.g. `Windows`)
- `grub.cfg` (GRUB loader configuration snippet)
- `limine.conf` (Limine loader configuration snippet)
- `bios.conf` (BIOS EFI `BOOT_ORDER` and `BOOT_NEXT` parameters)

These files are saved under `/config/www/boot/{pc_slug}/`, exposing them publicly over HTTP under your Home Assistant instance at `http://<your-ha-ip>:8123/local/boot/{pc_slug}/`.

---

## 🚀 Features

- 🖥️ **Multi-Bootloader Support**: Simultaneously updates **GRUB**, **Limine**, and **BIOS / UEFI NVRAM** configurations.
- ⚡ **BIOS Boot Mode Selection**: Toggle between **One-Time Boot (`BootNext`)** and **Persistent BIOS Boot Order (`BootOrder`)**.
- 🛠️ **Built-in Client Info Extractor**: Run `update_boot_selector.sh --info` on client PCs to easily extract all required IDs and config blocks for copy-pasting.

---

## 📦 Installation

### Via HACS (Recommended)
1. Open **HACS** in Home Assistant.
2. Click the top-right menu and choose **Custom repositories**.
3. Add `https://github.com/Bluscream/pc_boot_selector-hass` as an **Integration**.
4. Click **Add** and search for **PC Boot Selector** to install it.
5. Restart Home Assistant.

### Manual Installation
1. Copy the `custom_components/pc_boot_selector/` directory into your Home Assistant `/config/custom_components/` folder.
2. Restart Home Assistant.

---

## ⚙️ Configuration

1. In Home Assistant, go to **Settings** -> **Devices & Services**.
2. Click **Add Integration** and search for **PC Boot Selector**.
3. Fill in the basic settings:
   - **PC Name**: Friendly name (e.g. `Gaming PC`).
   - **Output Directory**: Output path (defaults to `/config/www/boot/{slug}/`).
   - **Timeout**: Default boot timeout in seconds.
4. Add your operating system boot options:
   - **OS Name**: Friendly name (e.g. `Bazzite`, `Windows`).
   - **GRUB Entry ID**: GRUB menu ID / title.
   - **EFI Boot Number**: 4-digit BIOS boot number from `efibootmgr` (e.g., `0002` for `Boot0002`).
   - **Limine Entry Config**: Multi-line Limine configuration snippet.

---

## 💡 Extracting Client Configs (`update_boot_selector.sh --info`)

To easily retrieve the **EFI Boot Numbers**, **GRUB IDs**, and **Limine Blocks** from your client PC, run the client update script with the `--info` or `-i` flag:

```bash
/usr/local/bin/update_boot_selector.sh --info
```

### Sample Extractor Output:
```text
--- 1. EFI Boot Numbers (BIOS) ---
  * Name: Limine       -> EFI Boot Number : 0001
  * Name: Fedora       -> EFI Boot Number : 0002
  * Name: Windows      -> EFI Boot Number : 0006

--- 2. GRUB Entry IDs ---
  * BLS Title          -> GRUB ID : Bazzite (ostree:0)

--- 3. Limine Entry Blocks ---
/Windows
    protocol: efi_chainload
    image_path: guid(2E39665E-E798-4C29-A9EF-A28E3F248290):/efi/Microsoft/Boot/bootmgfw.efi
```

---

## 🖥️ Client PC Setup

On the client PC, run `/usr/local/bin/update_boot_selector.sh` to fetch configurations from Home Assistant.

### Script Command Options:
```bash
# Default (no args): Fetch and update GRUB & Limine configs only
/usr/local/bin/update_boot_selector.sh

# Update BIOS/UEFI NVRAM (sets one-time BootNext)
/usr/local/bin/update_boot_selector.sh --bios

# Update BIOS/UEFI NVRAM and make persistent BootOrder changes
/usr/local/bin/update_boot_selector.sh --bios --always

# Extract copy/paste field values for Home Assistant setup
/usr/local/bin/update_boot_selector.sh --info
```

curl -s -f -o /boot/limine.conf "http://${HA_IP}:${HA_PORT}/local/boot/${PC_SLUG}/limine.conf"
curl -s -f -o /boot/grub2/remote_grub.cfg "http://${HA_IP}:${HA_PORT}/local/boot/${PC_SLUG}/grub.cfg"
curl -s -f -o /boot/bios.conf "http://${HA_IP}:${HA_PORT}/local/boot/${PC_SLUG}/bios.conf"

# Apply BIOS / UEFI settings if efibootmgr is installed
if [ -f /boot/bios.conf ] && command -v efibootmgr >/dev/null 2>&1; then
    source /boot/bios.conf
    [ -n "$BOOT_NEXT" ] && efibootmgr -n "$BOOT_NEXT"
    [ -n "$BOOT_ORDER" ] && efibootmgr -o "$BOOT_ORDER"
fi
```
