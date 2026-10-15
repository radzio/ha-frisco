"""The Frisco integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FriscoClient
from .const import CONF_PASSWORD, CONF_USER_ID, CONF_USERNAME, CONF_VISITOR_ID
from .coordinator import FriscoCoordinator

PLATFORMS = [Platform.SENSOR, Platform.DEVICE_TRACKER]

type FriscoConfigEntry = ConfigEntry[FriscoCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: FriscoConfigEntry) -> bool:
    """Set up Frisco from a config entry."""
    client = FriscoClient(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        visitor_id=entry.data.get(CONF_VISITOR_ID),
        user_id=entry.data.get(CONF_USER_ID),
    )

    coordinator = FriscoCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FriscoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
