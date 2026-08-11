import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from .const import DOMAIN
from .manager import PCBootManager

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SELECT, Platform.NUMBER]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the PC Boot Selector component."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PC Boot Selector from a config entry."""
    _LOGGER.info("Setting up PC Boot Selector entry: %s", entry.title)

    # Initialize manager with config entry data
    manager = PCBootManager(
        name=entry.data["name"],
        boot_dir=entry.data["boot_dir"],
        timeout=entry.data["timeout"],
        entries=entry.data["entries"],
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "manager": manager
    }

    # Read configuration in executor to prevent event loop blocking
    await hass.async_add_executor_job(manager.read_config)

    # Ensure configuration files on disk are written/updated immediately
    await hass.async_add_executor_job(
        manager.write_config, manager.current_os, manager.current_timeout, manager.current_boot_mode
    )

    # Register update listener to reload integration on options save

    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options/data update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
