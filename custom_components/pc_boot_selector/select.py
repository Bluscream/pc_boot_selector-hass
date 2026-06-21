import logging
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .manager import PCBootManager

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the select platform from a config entry."""
    manager: PCBootManager = hass.data[DOMAIN][entry.entry_id]["manager"]
    async_add_entities([PCBootSelectorSelect(entry, manager)], True)


class PCBootSelectorSelect(SelectEntity):
    """Representation of the PC Boot Selector select entity."""

    _attr_has_entity_name = True
    _attr_name = "Boot Selector"
    _attr_icon = "mdi:restart"

    def __init__(self, entry: ConfigEntry, manager: PCBootManager) -> None:
        """Initialize the select entity."""
        self._manager = manager
        self._attr_unique_id = f"{entry.entry_id}_os"
        self._attr_options = manager.os_options
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=manager.name,
            manufacturer="GRUB & Limine",
            model="Network Boot Selector",
        )

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option."""
        return self._manager.current_os

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option not in self._attr_options:
            return
        
        # Write updated files in executor
        await self.hass.async_add_executor_job(
            self._manager.write_config, option, self._manager.current_timeout
        )
        self.async_write_ha_state()
