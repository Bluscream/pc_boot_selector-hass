#!/bin/bash

# PC Boot Selector Client Script
# Can be installed using: sudo bash update_boot_selector.sh --install

CONF_FILE="/etc/pc-boot-selector.conf"

# Default configuration values
HA_URL="http://192.168.2.4:8123"
PC_SLUG="blu-pc"
ESP_UUID="1E87-C252"
UPDATE_BIOS=true
UPDATE_ALWAYS=false
RETRY_COUNT=5
RETRY_DELAY=2

# Load persistent config if available
if [ -f "$CONF_FILE" ]; then
    # shellcheck source=/dev/null
    source "$CONF_FILE"
fi

# Local target paths
GRUB_CACHE="/boot/grub2/remote_grub.cfg"
CUSTOM_CFG="/boot/grub2/custom.cfg"
LIMINE_CACHE="/boot/limine.conf"
BIOS_CACHE="/boot/bios.conf"

show_info() {
    python3 - << 'EOF'
import subprocess, re, os

def get_efiboot():
    efiboot = {}
    try:
        res = subprocess.run(["efibootmgr"], capture_output=True, text=True)
        out = res.stdout
        if not out:
            res = subprocess.run(["sudo", "efibootmgr"], capture_output=True, text=True)
            out = res.stdout
        for line in out.splitlines():
            m = re.match(r"^Boot([0-9A-Fa-f]{4})\*?\s+(.*)", line)
            if m:
                num, label = m.group(1), m.group(2).strip()
                efiboot[num] = label
    except Exception:
        pass
    return efiboot

def get_grub_entries():
    grub_entries = []
    paths = ["/boot/grub2/grub.cfg", "/boot/grub/grub.cfg", "/boot/efi/EFI/fedora/grub.cfg"]
    
    lines = []
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    lines.extend(f.readlines())
            except Exception:
                try:
                    res = subprocess.run(["sudo", "cat", path], capture_output=True, text=True)
                    lines.extend(res.stdout.splitlines())
                except Exception:
                    pass

    bls_dir = "/boot/loader/entries"
    if os.path.exists(bls_dir):
        try:
            for fname in sorted(os.listdir(bls_dir)):
                if fname.endswith(".conf"):
                    try:
                        with open(os.path.join(bls_dir, fname)) as f:
                            for l in f:
                                if l.startswith("title "):
                                    title = l.replace("title ", "").strip()
                                    grub_entries.append({"title": title, "id": title})
                    except Exception:
                        pass
        except Exception:
            pass

    for line in lines:
        if "menuentry" in line and not "function" in line:
            m = re.search(r"menuentry ['\"]([^'\"]+)['\"]", line)
            if m:
                title = m.group(1)
                id_m = re.search(r"['\"]([^'\"]+)['\"]\s*\{", line)
                gid = id_m.group(1) if id_m else title
                if not any(g["id"] == gid for g in grub_entries):
                    grub_entries.append({"title": title, "id": gid})

    return grub_entries

def get_limine_sections():
    limine_file = "/boot/limine.conf"
    if not os.path.exists(limine_file):
        limine_file = "/tmp/limine_esp/limine.conf"
    if not os.path.exists(limine_file):
        return {}

    limine_sections = {}
    try:
        with open(limine_file) as f:
            content = f.read()
        entries = re.split(r"\n(?=/[A-Za-z0-9_\-]+)", content)
        for entry in entries:
            entry = entry.strip()
            if entry.startswith("/"):
                lines = entry.split("\n")
                name = lines[0].lstrip("/").strip()
                body = []
                for l in lines[1:]:
                    if l.startswith("    "):
                        body.append(l[4:])
                    elif l.startswith("\t"):
                        body.append(l[1:])
                    else:
                        body.append(l)
                limine_sections[name] = "\n".join(body).strip()
    except Exception:
        pass
    return limine_sections

def main():
    efiboot = get_efiboot()
    grub_entries = get_grub_entries()
    limine_sections = get_limine_sections()

    target_entries = []
    
    # 1. Check for ostree entries in GRUB
    ostree_entries = [g for g in grub_entries if "ostree" in g["title"].lower()]
    if ostree_entries:
        for g in ostree_entries:
            target_entries.append({
                "name": g["title"],
                "grub_id": g["id"],
                "limine_key": "Bazzite",
                "default_efi": "0002"
            })

    # 2. Add Windows
    if "Windows" in limine_sections or any("windows" in g["title"].lower() for g in grub_entries):
        target_entries.append({
            "name": "Windows",
            "grub_id": "osprober-efi-7C59-B0E8",
            "limine_key": "Windows",
            "default_efi": "0006"
        })

    # 3. Add CachyOS / other Limine sections
    ignored_limine_keys = {"windows", "bazzite", "boot from usb", "boot from cd/dvd", "boot_from_usb", "boot_from_cddvd"}
    for l_key in limine_sections:
        if l_key.lower() not in ignored_limine_keys and not any(t["name"].lower() == l_key.lower() for t in target_entries):
            target_entries.append({
                "name": l_key,
                "grub_id": l_key.lower().replace(" ", "_"),
                "limine_key": l_key,
                "default_efi": "0001"
            })

    # 4. Add USB Boot entry if not present
    if not any("usb" in t["name"].lower() for t in target_entries):
        target_entries.append({
            "name": "Boot from USB",
            "grub_id": "boot_usb",
            "limine_key": "Boot_from_USB",
            "limine_custom": "protocol: efi_chainload\nimage_path: boot():/EFI/BOOT/BOOTX64.EFI",
            "default_efi": "0009"
        })

    # 5. Add CD/DVD Boot entry if not present
    if not any("cd/dvd" in t["name"].lower() or "cddvd" in t["name"].lower() for t in target_entries):
        target_entries.append({
            "name": "Boot from CD/DVD",
            "grub_id": "boot_cddvd",
            "limine_key": "Boot_from_CDDVD",
            "limine_custom": "protocol: efi_chainload\nimage_path: boot():/EFI/BOOT/BOOTX64.EFI",
            "default_efi": "0008"
        })

    print("=========================================================================")
    print("       PC Boot Selector - Home Assistant Copy/Paste Helper               ")
    print("=========================================================================")
    print("Copy these exact field values into Home Assistant Add/Edit Boot Entry:\n")

    for entry in target_entries:
        name = entry["name"]
        name_l = name.lower()
        lim_key = entry["limine_key"]
        gid = entry["grub_id"]
        default_efi = entry.get("default_efi", "0001")
        lim_custom = entry.get("limine_custom", None)

        # Match EFI Boot Number
        efi_match = "N/A"
        for num, label in efiboot.items():
            clean_l = label.lower()
            if "bazzite" in name_l or "fedora" in name_l:
                if "fedora" in clean_l or "bazzite" in clean_l:
                    efi_match = num
                    break
            elif "windows" in name_l:
                if "windows" in clean_l:
                    efi_match = num
                    break
            elif "cachyos" in name_l or "cachy" in name_l:
                if "limine" in clean_l or "cachy" in clean_l or "uefi os" in clean_l:
                    efi_match = num
                    break
            elif "usb" in name_l:
                if "usb" in clean_l or "removable" in clean_l:
                    efi_match = num
                    break
            elif "cd/dvd" in name_l or "cdrom" in name_l or "cddvd" in name_l:
                if "cd/dvd" in clean_l or "cdrom" in clean_l or "optical" in clean_l:
                    efi_match = num
                    break
            elif lim_key.lower() in clean_l:
                efi_match = num
                break

        if efi_match == "N/A":
            efi_match = default_efi

        print(f"---------------------- [ {name} ] ----------------------")
        print(f"Operating System Name (os_name)      : {name}")
        print(f"GRUB Entry ID / Name (grub_id)       : {gid}")
        print(f"EFI Boot Number (efi_boot_num)       : {efi_match}")

        # Limine Config Block
        lim_block = lim_custom if lim_custom else limine_sections.get(lim_key, "protocol: efi_chainload\nimage_path: boot():/EFI/BOOT/BOOTX64.EFI")
        print("Limine Entry Config Block (limine_config) :")
        print(lim_block)
        print()

    print("=========================================================================")

if __name__ == "__main__":
    main()
EOF
}

do_install() {
    echo "========================================================"
    echo "      Installing PC Boot Selector Client Service        "
    echo "========================================================"

    if [ "$EUID" -ne 0 ]; then
        echo "Error: Installation requires root privileges. Please run with sudo."
        exit 1
    fi

    # 1. Prompt for values if not set via flags
    if [ -z "$HA_URL_SET" ]; then
        read -r -p "Enter Home Assistant Base URL [default: $HA_URL]: " INPUT_URL
        if [ -n "$INPUT_URL" ]; then HA_URL="$INPUT_URL"; fi
    fi

    if [ -z "$PC_SLUG_SET" ]; then
        DEFAULT_SLUG=$(hostname | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | sed 's/^-//;s/-$//')
        read -r -p "Enter PC Slug [default: ${DEFAULT_SLUG:-blu-pc}]: " INPUT_SLUG
        if [ -n "$INPUT_SLUG" ]; then PC_SLUG="$INPUT_SLUG"; else PC_SLUG="${DEFAULT_SLUG:-blu-pc}"; fi
    fi

    # 2. Write configuration file
    mkdir -p /etc
    cat <<EOF > "$CONF_FILE"
# PC Boot Selector Client Configuration
HA_URL="${HA_URL}"
PC_SLUG="${PC_SLUG}"
ESP_UUID="${ESP_UUID}"
UPDATE_BIOS="${UPDATE_BIOS}"
UPDATE_ALWAYS="${UPDATE_ALWAYS}"
RETRY_COUNT=${RETRY_COUNT}
RETRY_DELAY=${RETRY_DELAY}
EOF
    echo "Created config file: $CONF_FILE"

    # 3. Copy script executable
    SCRIPT_TARGET="/usr/local/bin/update_boot_selector.sh"
    cp "$0" "$SCRIPT_TARGET" 2>/dev/null || cp "${BASH_SOURCE[0]}" "$SCRIPT_TARGET" 2>/dev/null
    chmod +x "$SCRIPT_TARGET"
    echo "Installed executable: $SCRIPT_TARGET"

    # 4. Create Systemd Service
    SERVICE_FILE="/etc/systemd/system/pc-boot-selector-update.service"
    cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Update PC Boot Selector Cache on Startup and Shutdown
After=network-online.target
Wants=network-online.target
DefaultDependencies=no
Before=shutdown.target reboot.target halt.target

[Service]
Type=oneshot
RemainAfterExit=true
ExecStart=/usr/local/bin/update_boot_selector.sh
ExecStop=/usr/local/bin/update_boot_selector.sh
StandardOutput=journal

[Install]
WantedBy=multi-user.target
EOF
    echo "Created systemd service: $SERVICE_FILE"

    # 5. Enable and start systemd service
    if command -v systemctl >/dev/null 2>&1; then
        systemctl daemon-reload
        systemctl enable pc-boot-selector-update.service
        echo "Enabled pc-boot-selector-update.service!"
    fi

    echo ""
    echo "Installation complete!"
    echo "Target URL: ${HA_URL}/local/boot/${PC_SLUG}/"
    echo "You can run 'sudo update_boot_selector.sh --info' to extract boot parameters for Home Assistant."
    exit 0
}

# Command line option parsing
SHOW_INFO=false
DO_INSTALL=false
HA_URL_SET=""
PC_SLUG_SET=""

while [ $# -gt 0 ]; do
    case "$1" in
        --install|-ins|install)
            DO_INSTALL=true
            shift
            ;;
        --url|-u)
            HA_URL="$2"
            HA_URL_SET=true
            shift 2
            ;;
        --slug|-s)
            PC_SLUG="$2"
            PC_SLUG_SET=true
            shift 2
            ;;
        -i|--info|info)
            SHOW_INFO=true
            shift
            ;;
        -b|--bios|bios)
            UPDATE_BIOS=true
            shift
            ;;
        --no-bios)
            UPDATE_BIOS=false
            shift
            ;;
        -a|--always|--persistent|always)
            UPDATE_ALWAYS=true
            shift
            ;;
        --one-time)
            UPDATE_ALWAYS=false
            shift
            ;;
        -h|--help|help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --install, -ins     Install script as a systemd service (/etc/systemd/system/pc-boot-selector-update.service)"
            echo "  -u, --url <URL>     Specify Home Assistant URL (e.g. http://192.168.2.4:8123)"
            echo "  -s, --slug <SLUG>   Specify PC Slug (e.g. blu-pc)"
            echo "  -i, --info          Extract and print formatted boot entry fields for Home Assistant"
            echo "  -b, --bios          Enable updating BIOS/UEFI NVRAM settings"
            echo "  --no-bios           Disable updating BIOS/UEFI NVRAM settings"
            echo "  -a, --always        Apply persistent changes across GRUB (grubenv) and BIOS (BootOrder)"
            echo "  --one-time          Apply one-time boot changes only (BootNext / grub-reboot)"
            echo "  -h, --help          Show this help message"
            echo "  (no args)           Fetch and apply configured boot targets"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

if [ "$DO_INSTALL" = true ]; then
    do_install
fi

if [ "$SHOW_INFO" = true ]; then
    show_info
    exit 0
fi

# Helper function: fetch URL with retries to a temp file, then move to destination
fetch_with_retry() {
    local url="$1"
    local dest="$2"
    local label="$3"
    local attempt=1
    local dest_dir
    dest_dir=$(dirname "$dest")
    local tmp_file
    tmp_file="/tmp/pc_boot_$(basename "$dest").tmp"

    while [ "$attempt" -le "$RETRY_COUNT" ]; do
        if curl -s -f -m 5 -o "$tmp_file" "$url"; then
            if [ "$EUID" -ne 0 ] && [ ! -w "$dest_dir" ] && [ ! -w "$dest" ]; then
                echo "Successfully fetched $label from Home Assistant (Note: write to $dest skipped without root privileges)."
                rm -f "$tmp_file"
                return 0
            fi
            if mv "$tmp_file" "$dest" 2>/dev/null || cp "$tmp_file" "$dest" 2>/dev/null; then
                rm -f "$tmp_file"
                echo "Successfully updated $label cache."
                return 0
            else
                echo "Fetched $label successfully, but failed to write to $dest."
                rm -f "$tmp_file"
                return 1
            fi
        fi
        if [ "$attempt" -lt "$RETRY_COUNT" ]; then
            sleep "$RETRY_DELAY"
        fi
        attempt=$((attempt + 1))
    done
    echo "Failed to fetch $label from Home Assistant ($url) after $RETRY_COUNT attempts."
    rm -f "$tmp_file"
    return 1
}

# Strip trailing slash from HA_URL if present
HA_URL="${HA_URL%/}"

GRUB_URL="${HA_URL}/local/boot/${PC_SLUG}/grub.cfg"
LIMINE_URL="${HA_URL}/local/boot/${PC_SLUG}/limine.conf"
BIOS_URL="${HA_URL}/local/boot/${PC_SLUG}/bios.conf"

echo "Updating PC Boot Selector configs from ${HA_URL}/local/boot/${PC_SLUG}/..."

# 1. Update GRUB Cache & Environment
if fetch_with_retry "$GRUB_URL" "$GRUB_CACHE" "GRUB"; then
    # Configure /boot/grub2/custom.cfg to load local cache with live network fallback
    if [ -d "/boot/grub2" ] && [ -w "/boot/grub2" ]; then
        HA_HOST_PORT=$(echo "$HA_URL" | sed -E 's#^https?://([^/]+).*#\1#')
        cat <<EOF > "$CUSTOM_CFG"
# PC Boot Selector GRUB Master Config
# Automatically generated by update_boot_selector.sh

# 1. Restore Background Theme
if [ -f \${prefix}/background.jpg ]; then
    insmod jpeg
    insmod png
    background_image \${prefix}/background.jpg
elif [ -f /boot/grub2/background.jpg ]; then
    insmod jpeg
    insmod png
    background_image /boot/grub2/background.jpg
fi

set boot_cfg_source=""

# 2. Live network fallback (checks Home Assistant live during UEFI boot if network is active)
if [ -n "\$net_default_server" ] || net_bootp; then
    if [ -f (http,${HA_HOST_PORT})/local/boot/${PC_SLUG}/grub.cfg ]; then
        source (http,${HA_HOST_PORT})/local/boot/${PC_SLUG}/grub.cfg
        set boot_cfg_source="live"
        echo "[PC Boot Selector] Loaded LIVE configuration from Home Assistant directly"
    fi
fi

# 3. Load locally cached configuration (downloaded previously)
if [ -z "\$boot_cfg_source" ]; then
    if [ -f \${prefix}/remote_grub.cfg ]; then
        source \${prefix}/remote_grub.cfg
        set boot_cfg_source="cached"
        echo "[PC Boot Selector] Loaded cached Home Assistant configuration (downloaded previously)"
    elif [ -f /boot/grub2/remote_grub.cfg ]; then
        source /boot/grub2/remote_grub.cfg
        set boot_cfg_source="cached"
        echo "[PC Boot Selector] Loaded cached Home Assistant configuration (downloaded previously)"
    fi
fi

# 4. Fallback to own local GRUB default
if [ -z "\$boot_cfg_source" ]; then
    echo "[PC Boot Selector] Using local GRUB default configuration only"
fi

echo "[PC Boot Selector] Target Default: \${default} (Timeout: \${timeout}s)"
sleep 2
EOF
    fi

    if [ -f "$GRUB_CACHE" ]; then
        GRUB_DEFAULT=$(grep -E '^set default=' "$GRUB_CACHE" | sed -E 's/set default="?([^"]+)"?/\1/' | tr -d '\r')
        if [ -n "$GRUB_DEFAULT" ]; then
            GRUB_REBOOT_CMD=""
            GRUB_SET_DEFAULT_CMD=""
            command -v grub2-reboot >/dev/null 2>&1 && GRUB_REBOOT_CMD="grub2-reboot"
            command -v grub-reboot >/dev/null 2>&1 && GRUB_REBOOT_CMD="grub-reboot"
            command -v grub2-set-default >/dev/null 2>&1 && GRUB_SET_DEFAULT_CMD="grub2-set-default"
            command -v grub-set-default >/dev/null 2>&1 && GRUB_SET_DEFAULT_CMD="grub-set-default"

            if [ "$UPDATE_ALWAYS" = true ] || [ "$UPDATE_ALWAYS" = "1" ]; then
                if [ -n "$GRUB_SET_DEFAULT_CMD" ]; then
                    echo "Setting persistent GRUB default to: $GRUB_DEFAULT"
                    $GRUB_SET_DEFAULT_CMD "$GRUB_DEFAULT" >/dev/null 2>&1 || echo "Failed to set persistent GRUB default"
                fi
            else
                if [ -n "$GRUB_REBOOT_CMD" ]; then
                    echo "Setting one-time GRUB reboot entry to: $GRUB_DEFAULT"
                    $GRUB_REBOOT_CMD "$GRUB_DEFAULT" >/dev/null 2>&1 || echo "Failed to set one-time GRUB reboot entry"
                fi
            fi
        fi
    fi
fi

# 2. Update Limine Cache
fetch_with_retry "$LIMINE_URL" "$LIMINE_CACHE" "Limine"

# 3. Update Limine ESP Cache by mounting it dynamically by UUID if set
if [ -n "$ESP_UUID" ] && [ "$EUID" -eq 0 ]; then
    ESP_MOUNT="/tmp/limine_esp"
    mkdir -p "$ESP_MOUNT"
    if mount -U "$ESP_UUID" "$ESP_MOUNT" 2>/dev/null || mount "/dev/disk/by-uuid/$ESP_UUID" "$ESP_MOUNT" 2>/dev/null; then
        fetch_with_retry "$LIMINE_URL" "$ESP_MOUNT/limine.conf" "Limine ESP"
        umount "$ESP_MOUNT" 2>/dev/null
    fi
    rmdir "$ESP_MOUNT" 2>/dev/null
fi

# 4. Update BIOS/UEFI Boot Settings (If enabled)
if [ "$UPDATE_BIOS" = true ] || [ "$UPDATE_BIOS" = "1" ]; then
    if fetch_with_retry "$BIOS_URL" "$BIOS_CACHE" "BIOS"; then
        if command -v efibootmgr >/dev/null 2>&1 && [ -f "$BIOS_CACHE" ]; then
            BOOT_ORDER=""
            BOOT_NEXT=""
            # shellcheck source=/dev/null
            source "$BIOS_CACHE"

            # Set One-Time BootNext if specified
            if [ -n "$BOOT_NEXT" ]; then
                echo "Setting EFI BootNext to: $BOOT_NEXT"
                efibootmgr -n "$BOOT_NEXT" >/dev/null 2>&1 || echo "Failed to set BootNext (requires root / privileges)"
            fi

            # Apply persistent BootOrder only if UPDATE_ALWAYS is enabled
            if [ "$UPDATE_ALWAYS" = true ] || [ "$UPDATE_ALWAYS" = "1" ]; then
                if [ -n "$BOOT_ORDER" ]; then
                    EXISTING_BOOT_IDS=$(efibootmgr | grep -E "^Boot[0-9A-Fa-f]{4}" | sed -E 's/^Boot([0-9A-Fa-f]{4}).*/\1/' | tr '\n' ' ')
                    FILTERED_ORDER=""
                    IFS=',' read -ra ADDR <<< "$BOOT_ORDER"
                    for id in "${ADDR[@]}"; do
                        if echo " $EXISTING_BOOT_IDS " | grep -q " $id "; then
                            if [ -z "$FILTERED_ORDER" ]; then
                                FILTERED_ORDER="$id"
                            else
                                FILTERED_ORDER="${FILTERED_ORDER},$id"
                            fi
                        fi
                    done

                    CURRENT_ORDER=$(efibootmgr | grep -i "BootOrder:" | awk '{print $2}' | tr -d '\r')
                    if [ -n "$FILTERED_ORDER" ] && [ "$CURRENT_ORDER" != "$FILTERED_ORDER" ]; then
                        echo "Updating EFI BootOrder to: $FILTERED_ORDER (was: $CURRENT_ORDER)"
                        efibootmgr -o "$FILTERED_ORDER" >/dev/null 2>&1 || echo "Failed to set BootOrder"
                    fi
                fi
            fi
        fi
    fi
fi
