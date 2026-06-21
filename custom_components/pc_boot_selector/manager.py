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

        # Initial state setup: find OS options
        self.os_options = [entry["name"] for entry in entries]
        self.current_os = self.os_options[0] if self.os_options else ""

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

    def write_config(self, os_name: str, timeout: int) -> None:
        """Write the boot configuration to os.txt, grub.cfg, and limine.conf."""
        if os_name not in self.os_options:
            _LOGGER.error("[%s] Invalid OS selected: %s", self.name, os_name)
            return

        self.current_os = os_name
        self.current_timeout = timeout

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
            # default_entry is 1-based index of the entry from the top of the list
            # So if Windows is first, it's 1. Bazzite is 2. CachyOS is 3.
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
                # Add indentation to each line of the config block
                config_lines = entry["limine_config"].strip().split("\n")
                for line in config_lines:
                    if line.strip():
                        # If the line already starts with whitespace, keep it, otherwise add 4 spaces
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
