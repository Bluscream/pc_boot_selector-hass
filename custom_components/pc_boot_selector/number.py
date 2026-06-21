import logging
from homeassistant.components.number import NumberEntity
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
    """Set up the number platform from a config entry."""
    manager: PCBootManager = hass.data[DOMAIN][entry.entry_id]["manager"]
    async_add_entities([PCBootSelectorTimeoutNumber(entry, manager)], True)


class PCBootSelectorTimeoutNumber(NumberEntity):
    """Representation of the PC Boot Selector Timeout number entity."""

    _attr_has_entity_name = True
    _attr_name = "Boot Timeout"
    _attr_icon = "mdi:clock-outline"
    _attr_native_min_value = 0
    _attr_native_max_value = 60
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "s"

    def __init__(self, entry: ConfigEntry, manager: PCBootManager) -> None:
        """Initialize the number entity."""
        self._manager = manager
        self._attr_unique_id = f"{entry.entry_id}_timeout"
        
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=manager.name,
            manufacturer="GRUB & Limine",
            model="Network Boot Selector",
        )

    @property
    def native_value(self) -> float | None:
        """Return the state of the entity."""
        return float(self._manager.current_timeout)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        timeout_int = int(value)
        # Write updated files in executor
        await self.hass.async_add_executor_job(
            self._manager.write_config, self._manager.current_os, timeout_int
        )
        self.async_write_ha_state()
