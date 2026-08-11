import os
import re
import logging

_LOGGER = logging.getLogger(__name__)

class PCBootManager:
    """Manages reading and writing PC boot configuration files."""

    def __init__(self, name: str, boot_dir: str, timeout: int, entries: list[dict]) -> None:
        self.name = name
        self.boot_dir = boot_dir
        self.current_timeout = timeout
        self.entries = entries

        # File paths
        self.os_txt_path = os.path.join(boot_dir, "os.txt")
        self.grub_cfg_path = os.path.join(boot_dir, "grub.cfg")
        self.limine_conf_path = os.path.join(boot_dir, "limine.conf")
        self.bios_conf_path = os.path.join(boot_dir, "bios.conf")

        # Initial state setup: find OS options
        self.os_options = [entry["name"] for entry in entries]
        self.current_os = self.os_options[0] if self.os_options else ""
        self.current_boot_mode = "one_time"

    def read_config(self) -> None:
        """Read the boot configuration from files on disk."""
        # 1. Read OS from os.txt
        if os.path.exists(self.os_txt_path):
            try:
                with open(self.os_txt_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content in self.os_options:
                    self.current_os = content
                _LOGGER.info("[%s] Read current OS from os.txt: %s", self.name, self.current_os)
            except Exception as err:
                _LOGGER.error("[%s] Failed to read os.txt: %s", self.name, err)

        # 2. Read Timeout from grub.cfg
        if os.path.exists(self.grub_cfg_path):
            try:
                with open(self.grub_cfg_path, "r", encoding="utf-8") as f:
                    content = f.read()
                match = re.search(r"set timeout=(\d+)", content)
                if match:
                    self.current_timeout = int(match.group(1))
                    _LOGGER.info("[%s] Read current timeout from grub.cfg: %d", self.name, self.current_timeout)
            except Exception as err:
                _LOGGER.error("[%s] Failed to read grub.cfg: %s", self.name, err)

        # 3. Read Bios Config if available
        if os.path.exists(self.bios_conf_path):
            try:
                with open(self.bios_conf_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if "BOOT_NEXT=" in content and not 'BOOT_NEXT=""' in content and not "BOOT_NEXT=''" in content:
                    self.current_boot_mode = "one_time"
            except Exception as err:
                _LOGGER.error("[%s] Failed to read bios.conf: %s", self.name, err)

    def write_config(self, os_name: str, timeout: int, boot_mode: str = "one_time") -> None:
        """Write the boot configuration to os.txt, grub.cfg, limine.conf, and bios.conf."""
        if os_name not in self.os_options:
            _LOGGER.error("[%s] Invalid OS selected: %s", self.name, os_name)
            return

        self.current_os = os_name
        self.current_timeout = timeout
        self.current_boot_mode = boot_mode

        # Find entry settings
        selected_entry = None
        for entry in self.entries:
            if entry["name"] == os_name:
                selected_entry = entry
                break

        if not selected_entry:
            return

        # Ensure directory exists
        os.makedirs(self.boot_dir, exist_ok=True)

        # 1. Write os.txt
        try:
            with open(self.os_txt_path, "w", encoding="utf-8") as f:
                f.write(f"{os_name}\n")
            _LOGGER.info("[%s] Successfully wrote %s to %s", self.name, os_name, self.os_txt_path)
        except Exception as err:
            _LOGGER.error("[%s] Failed to write os.txt: %s", self.name, err)

        # 2. Write grub.cfg
        try:
            grub_content = (
                f'set default="{selected_entry["grub_id"]}"\n'
                f'set timeout={timeout}\n'
            )
            with open(self.grub_cfg_path, "w", encoding="utf-8") as f:
                f.write(grub_content)
            _LOGGER.info("[%s] Successfully wrote grub.cfg default=%s, timeout=%d", self.name, selected_entry["grub_id"], timeout)
        except Exception as err:
            _LOGGER.error("[%s] Failed to write grub.cfg: %s", self.name, err)

        # 3. Write limine.conf
        try:
            # Build entries layout dynamically
            default_entry_index = 1
            for index, entry in enumerate(self.entries):
                if entry["name"] == os_name:
                    default_entry_index = index + 1
                    break

            limine_content = (
                f"timeout: {timeout}\n"
                f"default_entry: {default_entry_index}\n"
                "remember_last_entry: yes\n\n"
            )

            # Loop through entries and add them
            for entry in self.entries:
                limine_content += f"/{entry['name']}\n"
                config_lines = entry["limine_config"].strip().split("\n")
                for line in config_lines:
                    if line.strip():
                        if line.startswith(" ") or line.startswith("\t"):
                            limine_content += f"{line}\n"
                        else:
                            limine_content += f"    {line}\n"
                limine_content += "\n"

            with open(self.limine_conf_path, "w", encoding="utf-8") as f:
                f.write(limine_content)
            _LOGGER.info("[%s] Successfully wrote limine.conf default_entry=%d, timeout=%d", self.name, default_entry_index, timeout)
        except Exception as err:
            _LOGGER.error("[%s] Failed to write limine.conf: %s", self.name, err)

        # 4. Write bios.conf
        try:
            efi_num = selected_entry.get("efi_boot_num", "").strip()
            
            # Construct ordered EFI numbers
            boot_nums = []
            if efi_num:
                boot_nums.append(efi_num)
            for entry in self.entries:
                num = entry.get("efi_boot_num", "").strip()
                if num and num not in boot_nums:
                    boot_nums.append(num)

            boot_order_str = ",".join(boot_nums)
            boot_next_str = efi_num if (boot_mode == "one_time" and efi_num) else ""

            bios_content = (
                f'# PC Boot Selector BIOS Config\n'
                f'BOOT_ORDER="{boot_order_str}"\n'
                f'BOOT_NEXT="{boot_next_str}"\n'
                f'SELECTED_OS="{os_name}"\n'
            )

            with open(self.bios_conf_path, "w", encoding="utf-8") as f:
                f.write(bios_content)
            _LOGGER.info("[%s] Successfully wrote bios.conf BOOT_ORDER='%s', BOOT_NEXT='%s'", self.name, boot_order_str, boot_next_str)
        except Exception as err:
            _LOGGER.error("[%s] Failed to write bios.conf: %s", self.name, err)

        # 5. Copy client script to boot_dir so clients can download it directly
        try:
            src_script = os.path.join(os.path.dirname(__file__), "update_boot_selector.sh")
            dst_script = os.path.join(self.boot_dir, "update_boot_selector.sh")
            if os.path.exists(src_script):
                with open(src_script, "r", encoding="utf-8") as f_in:
                    script_data = f_in.read()
                with open(dst_script, "w", encoding="utf-8") as f_out:
                    f_out.write(script_data)
                os.chmod(dst_script, 0o755)
                _LOGGER.info("[%s] Successfully copied update_boot_selector.sh to %s", self.name, dst_script)
        except Exception as err:
            _LOGGER.error("[%s] Failed to copy update_boot_selector.sh: %s", self.name, err)

        # 6. Write index.html
        try:
            index_html_path = os.path.join(self.boot_dir, "index.html")
            index_content = (
                "<!DOCTYPE html>\n"
                "<html>\n"
                "<head>\n"
                '  <meta charset="utf-8">\n'
                f"  <title>PC Boot Selector - {self.name}</title>\n"
                "  <style>\n"
                "    body { font-family: system-ui, sans-serif; margin: 2rem; background: #0f172a; color: #f8fafc; line-height: 1.5; }\n"
                "    h1 { color: #38bdf8; font-size: 1.6rem; }\n"
                "    h2 { color: #94a3b8; font-size: 1.2rem; margin-top: 1.5rem; }\n"
                "    ul { list-style: none; padding: 0; }\n"
                "    li { margin: 0.5rem 0; }\n"
                "    a { color: #38bdf8; text-decoration: none; font-weight: bold; font-size: 1.05rem; }\n"
                "    a:hover { text-decoration: underline; color: #7dd3fc; }\n"
                "    .badge { background: #1e293b; padding: 0.2rem 0.5rem; border-radius: 4px; color: #94a3b8; font-size: 0.85rem; margin-left: 0.5rem; }\n"
                "    pre { background: #1e293b; padding: 1rem; border-radius: 6px; overflow-x: auto; color: #38bdf8; font-size: 0.9rem; }\n"
                "  </style>\n"
                "</head>\n"
                "<body>\n"
                f"  <h1>🖥️ PC Boot Selector: {self.name}</h1>\n"
                f"  <p>Current Target OS: <strong>{os_name}</strong> | Boot Mode: <strong>{boot_mode}</strong></p>\n"
                "  <hr style='border-color: #334155;'>\n"
                "  <h2>📄 Generated Configuration Files</h2>\n"
                "  <ul>\n"
                '    <li><a href="os.txt">os.txt</a> <span class="badge">Plain Text OS Name</span></li>\n'
                '    <li><a href="grub.cfg">grub.cfg</a> <span class="badge">GRUB Config</span></li>\n'
                '    <li><a href="limine.conf">limine.conf</a> <span class="badge">Limine Config</span></li>\n'
                '    <li><a href="bios.conf">bios.conf</a> <span class="badge">BIOS / UEFI BootOrder & BootNext</span></li>\n'
                '    <li><a href="update_boot_selector.sh">update_boot_selector.sh</a> <span class="badge">Client Setup Script</span></li>\n'
                "  </ul>\n"
                "  <h2>⚡ One-Line Client Installation Command</h2>\n"
                "  <p>Run the following command on your client PC to download & install the update service:</p>\n"
                "  <pre>wget -O /tmp/update_boot_selector.sh update_boot_selector.sh &amp;&amp; sudo bash /tmp/update_boot_selector.sh --install</pre>\n"
                "</body>\n"
                "</html>\n"
            )
            with open(index_html_path, "w", encoding="utf-8") as f:
                f.write(index_content)
            _LOGGER.info("[%s] Successfully wrote index.html", self.name)
        except Exception as err:
            _LOGGER.error("[%s] Failed to write index.html: %s", self.name, err)


