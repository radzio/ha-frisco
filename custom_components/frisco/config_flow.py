"""Config flow for Frisco."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FriscoApiError, FriscoAuthError, FriscoClient
from .const import (
    CONF_PASSWORD,
    CONF_USER_ID,
    CONF_USERNAME,
    CONF_VISITOR_ID,
    DOMAIN,
)

STEP_USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class FriscoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Frisco."""

    VERSION = 1

    async def _validate(self, username: str, password: str) -> dict[str, Any]:
        """Log in to confirm credentials and capture the account ids."""
        client = FriscoClient(async_get_clientsession(self.hass), username, password)
        await client.async_login()
        return {
            CONF_USERNAME: username,
            CONF_PASSWORD: password,
            CONF_USER_ID: client.user_id,
            CONF_VISITOR_ID: client.visitor_id,
        }

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = await self._validate(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except FriscoAuthError:
                errors["base"] = "invalid_auth"
            except FriscoApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(data[CONF_USER_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=data[CONF_USERNAME], data=data
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                data = await self._validate(
                    reauth_entry.data[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except FriscoAuthError:
                errors["base"] = "invalid_auth"
            except FriscoApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry, data={**reauth_entry.data, **data}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={
                CONF_USERNAME: reauth_entry.data[CONF_USERNAME]
            },
        )
