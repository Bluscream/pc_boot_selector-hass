# PC Boot Selector for Home Assistant

A custom Home Assistant integration that enables selecting operating systems and adjusting boot timeouts for multiple PCs directly from your dashboard.

Whenever you change the selection or timeout in Home Assistant, the integration writes:
- `os.txt` (Nice name of the target OS, e.g., `Windows`)
- `grub.cfg` (GRUB loader configuration snippet)
- `limine.conf` (Limine loader configuration snippet)

These are saved under `/config/www/boot/{pc_name_slug}/`, exposing them via HTTP under your Home Assistant instance at `http://<your-ha-ip>:8123/local/boot/{pc_name_slug}/`.

---

## 🚀 Installation

### Via HACS (Recommended)
1. Go to **HACS** in Home Assistant.
2. Click the three dots in the top right and select **Custom repositories**.
3. Add `https://github.com/Bluscream/pc_boot_selector-hass` as an **Integration**.
4. Click **Add** and search for **PC Boot Selector** to install it.
5. Restart Home Assistant.

### Manual Installation
1. Copy the `custom_components/pc_boot_selector/` directory into your Home Assistant `/config/custom_components/` folder.
2. Restart Home Assistant.

---

## ⚙️ Configuration

1. In Home Assistant, go to **Settings** -> **Devices & Services**.
2. Click **Add Integration** in the bottom right.
3. Search for **PC Boot Selector** and select it.
4. Fill in the configuration flow:
   - **PC Name**: A friendly name for the target PC (e.g. `Gaming PC`).
   - **Output Path**: The directory where configuration files will be written (defaults to `/config/www/boot/{slug}/`).
   - **Timeout**: The default timeout in seconds.
5. In the next step, add your operating systems one by one:
   - **OS Name**: Friendly name (e.g. `Windows`, `Bazzite`, `CachyOS`).
   - **GRUB Entry ID**: The menu entry ID for this OS in GRUB.
   - **Limine Entry Config**: The multi-line Limine configuration parameters for this OS.
   - Check **Add another boot entry?** to keep adding operating systems, then submit.

---

## 🖥️ Client Setup Examples

On the PC that you wish to control, configure your bootloader to pull files dynamically from Home Assistant:

### 1. Limine Setup
You can configure Limine on your client PC to load the remote configuration:
```ini
# Add this to the top of your /boot/limine.conf or /boot/efi/limine.conf
# to retrieve the boot selection and timeout from Home Assistant

timeout: 5
default_entry: 1

# Configure network settings or load remote config via TFTP/HTTP (if supported by your network card/Limine version)
# Alternatively, use a script on shutdown/boot inside the OS to sync:
# wget -O /boot/limine.conf http://192.168.2.4:8123/local/boot/gaming_pc/limine.conf
```

### 2. GRUB Setup
Edit `/etc/grub.d/40_custom` on the client PC:
```bash
#!/bin/sh
exec tail -n +3 $0
# This file provides an easy way to add custom menu entries.  Simply type the
# menu entries you want to add after this comment.  Be careful not to change
# the 'exec tail' line above.

# Example startup sync script or menu inclusion:
# wget -O /boot/grub/remote_grub.cfg http://192.168.2.4:8123/local/boot/gaming_pc/grub.cfg
```
