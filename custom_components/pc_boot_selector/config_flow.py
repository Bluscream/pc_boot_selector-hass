import os
import logging
import voluptuous as vol
import textwrap

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import DOMAIN

from homeassistant.core import callback
from homeassistant.helpers.network import get_url, NoURLAvailableError

_LOGGER = logging.getLogger(__name__)

def get_base_url(hass) -> str:
    """Get the base URL of the Home Assistant instance."""
    try:
        return get_url(hass)
    except NoURLAvailableError:
        return "http://homeassistant.local:8123"

def check_dir(boot_dir: str) -> None:
    """Check if the directory is writable."""
    os.makedirs(boot_dir, exist_ok=True)
    test_file = os.path.join(boot_dir, ".write_test")
    with open(test_file, "w") as f:
        f.write("test")
    os.remove(test_file)


class PCBootSelectorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PC Boot Selector."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow for this handler."""
        return PCBootSelectorOptionsFlowHandler(config_entry)

    def __init__(self) -> None:
        """Initialize flow."""
        self._name: str | None = None
        self._boot_dir: str | None = None
        self._timeout: int = 5
        self._os_entries: list[dict] = []

    async def async_step_user(self, user_input=None):
        """Handle the first step of configuration."""
        errors = {}

        if user_input is not None:
            name = user_input["name"]
            slug = slugify(name)
            
            # Prevent duplicate instances with the same name
            await self.async_set_unique_id(slug)
            self._abort_if_unique_id_configured()

            boot_dir = user_input.get("boot_dir")
            if not boot_dir:
                boot_dir = f"/config/www/boot/{slug}/"

            # Check if the output directory is writable inside the executor
            try:
                await self.hass.async_add_executor_job(check_dir, boot_dir)
            except Exception as err:
                _LOGGER.error("Failed to write to directory %s: %s", boot_dir, err)
                errors["boot_dir"] = "invalid_dir"

            if not errors:
                self._name = name
                self._boot_dir = boot_dir
                self._timeout = user_input.get("timeout", 5)
                return await self.async_step_os_entry()

        schema = vol.Schema({
            vol.Required("name"): str,
            vol.Optional("boot_dir"): str,
            vol.Required("timeout", default=5): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_os_entry(self, user_input=None):
        """Handle the second step of configuration (adding boot entries)."""
        errors = {}

        if user_input is not None:
            limine_config = textwrap.dedent(user_input["limine_config"]).strip()
            self._os_entries.append({
                "name": user_input["os_name"],
                "grub_id": user_input["grub_id"],
                "efi_boot_num": user_input.get("efi_boot_num", "").strip(),
                "limine_config": limine_config,
            })

            # Loop back if the user wants to add another OS option
            if user_input.get("add_another"):
                return await self.async_step_os_entry()

            if not self._os_entries:
                errors["base"] = "empty_os_list"
            else:
                return await self.async_step_instructions()

        schema = vol.Schema({
            vol.Required("os_name"): str,
            vol.Required("grub_id"): str,
            vol.Optional("efi_boot_num", default=""): str,
            vol.Required("limine_config"): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)
            ),
            vol.Optional("add_another", default=False): bool,
        })

        return self.async_show_form(
            step_id="os_entry",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_instructions(self, user_input=None):
        """Show instructions for client setup before creating the entry."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._name,
                data={
                    "name": self._name,
                    "boot_dir": self._boot_dir,
                    "timeout": self._timeout,
                    "entries": self._os_entries,
                }
            )

        web_path = self._boot_dir
        if "www/" in web_path:
            web_path = web_path.split("www/", 1)[1]
        elif "www" in web_path:
            web_path = web_path.split("www", 1)[1]
        web_path = web_path.strip("/")

        base_url = get_base_url(self.hass)
        net_host = base_url.replace("http://", "").replace("https://", "").rstrip("/")
        placeholders = {
            "limine_url": f"{base_url}/local/{web_path}/limine.conf",
            "grub_url": f"{base_url}/local/{web_path}/grub.cfg",
            "grub_http_url": f"(http,{net_host})/local/{web_path}/grub.cfg",
            "bios_url": f"{base_url}/local/{web_path}/bios.conf",
            "os_url": f"{base_url}/local/{web_path}/os.txt",
        }

        return self.async_show_form(
            step_id="instructions",
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
        )



class PCBootSelectorOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for PC Boot Selector."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._name = config_entry.data.get("name")
        self._boot_dir = config_entry.data.get("boot_dir")
        self._timeout = config_entry.data.get("timeout", 5)
        self._os_entries = list(config_entry.data.get("entries", []))
        self._selected_os: str | None = None

    async def async_step_init(self, user_input=None):
        """Manage basic options."""
        errors = {}

        if user_input is not None:
            self._name = user_input["name"]
            self._boot_dir = user_input["boot_dir"]
            self._timeout = user_input["timeout"]
            return await self.async_step_manage_entries()

        schema = vol.Schema({
            vol.Required("name", default=self._name): str,
            vol.Required("boot_dir", default=self._boot_dir): str,
            vol.Required("timeout", default=self._timeout): vol.All(vol.Coerce(int), vol.Range(min=0, max=60)),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_manage_entries(self, user_input=None):
        """Manage individual boot entries."""
        if user_input is not None:
            selection = user_input["selection"]
            if selection == "done":
                return await self.async_step_instructions()

            if selection == "add_new":
                self._selected_os = None
                return await self.async_step_os_entry()

            self._selected_os = selection
            return await self.async_step_os_entry()

        options = {"add_new": "Add New Entry", "done": "Done / Save Changes"}
        for entry in self._os_entries:
            options[entry["name"]] = entry["name"]

        schema = vol.Schema({
            vol.Required("selection", default="done"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[selector.SelectOptionDict(value=k, label=v) for k, v in options.items()],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        })

        return self.async_show_form(step_id="manage_entries", data_schema=schema)

    async def async_step_instructions(self, user_input=None):
        """Show instructions for client setup before saving options."""
        if user_input is not None:
            new_data = {
                "name": self._name,
                "boot_dir": self._boot_dir,
                "timeout": self._timeout,
                "entries": self._os_entries,
            }
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        web_path = self._boot_dir
        if "www/" in web_path:
            web_path = web_path.split("www/", 1)[1]
        elif "www" in web_path:
            web_path = web_path.split("www", 1)[1]
        web_path = web_path.strip("/")

        base_url = get_base_url(self.hass)
        net_host = base_url.replace("http://", "").replace("https://", "").rstrip("/")
        placeholders = {
            "limine_url": f"{base_url}/local/{web_path}/limine.conf",
            "grub_url": f"{base_url}/local/{web_path}/grub.cfg",
            "grub_http_url": f"(http,{net_host})/local/{web_path}/grub.cfg",
            "bios_url": f"{base_url}/local/{web_path}/bios.conf",
            "os_url": f"{base_url}/local/{web_path}/os.txt",
        }

        return self.async_show_form(
            step_id="instructions",
            data_schema=vol.Schema({}),
            description_placeholders=placeholders,
        )

    async def async_step_os_entry(self, user_input=None):
        """Add or edit an operating system configuration."""
        errors = {}

        current_entry = None
        if self._selected_os:
            for entry in self._os_entries:
                if entry["name"] == self._selected_os:
                    current_entry = entry
                    break

        if user_input is not None:
            if user_input.get("delete_entry") and current_entry:
                self._os_entries.remove(current_entry)
            else:
                limine_config = textwrap.dedent(user_input["limine_config"]).strip()
                new_entry = {
                    "name": user_input["os_name"],
                    "grub_id": user_input["grub_id"],
                    "efi_boot_num": user_input.get("efi_boot_num", "").strip(),
                    "limine_config": limine_config,
                }
                if current_entry:
                    idx = self._os_entries.index(current_entry)
                    self._os_entries[idx] = new_entry
                else:
                    self._os_entries.append(new_entry)

            return await self.async_step_manage_entries()

        defaults = {}
        if current_entry:
            defaults["os_name"] = current_entry["name"]
            defaults["grub_id"] = current_entry["grub_id"]
            defaults["efi_boot_num"] = current_entry.get("efi_boot_num", "")
            defaults["limine_config"] = current_entry["limine_config"]

        schema_dict = {
            vol.Required("os_name", default=defaults.get("os_name", "")): str,
            vol.Required("grub_id", default=defaults.get("grub_id", "")): str,
            vol.Optional("efi_boot_num", default=defaults.get("efi_boot_num", "")): str,
            vol.Required("limine_config", default=defaults.get("limine_config", "")): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)
            ),
        }

        if current_entry:
            schema_dict[vol.Optional("delete_entry", default=False)] = bool

        schema = vol.Schema(schema_dict)

        return self.async_show_form(step_id="os_entry", data_schema=schema)

