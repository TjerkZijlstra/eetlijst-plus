"""Config flow for Eetlijst+."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectOptionDict,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import EetlijstApi, EetlijstAuthError, EetlijstError, clean_token
from .const import CONF_GROUP_ID, CONF_GROUP_NAME, DOMAIN, LOGGER

TOKEN_SCHEMA = vol.Schema(
    {vol.Required(CONF_TOKEN): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
)


class EetlijstConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the setup."""

    VERSION = 1

    def __init__(self) -> None:
        """Init."""
        self._token: str = ""
        self._user_id: str = ""
        self._groups: dict[str, str] = {}

    async def _validate(self, token: str) -> tuple[dict[str, str], EetlijstApi | None]:
        """Return (errors, api)."""
        api = EetlijstApi(async_get_clientsession(self.hass), clean_token(token))
        if not api.user_id:
            return {"base": "invalid_token"}, None
        try:
            groups = await api.get_groups()
        except EetlijstAuthError:
            return {"base": "invalid_auth"}, None
        except EetlijstError as err:
            LOGGER.warning("Eetlijst niet bereikbaar: %s", err)
            return {"base": "cannot_connect"}, None
        if not groups:
            return {"base": "no_groups"}, None
        self._groups = {g["id"]: g.get("name") or g["id"] for g in groups}
        return {}, api

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, api = await self._validate(user_input[CONF_TOKEN])
            if api is not None:
                self._token = api.token
                self._user_id = api.user_id or ""
                if len(self._groups) == 1:
                    return await self._create(next(iter(self._groups)))
                return await self.async_step_group()
        return self.async_show_form(step_id="user", data_schema=TOKEN_SCHEMA, errors=errors)

    async def async_step_group(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick a group when the user is in several."""
        if user_input is not None:
            return await self._create(user_input[CONF_GROUP_ID])
        options = [SelectOptionDict(value=k, label=v) for k, v in self._groups.items()]
        return self.async_show_form(
            step_id="group",
            data_schema=vol.Schema(
                {vol.Required(CONF_GROUP_ID): SelectSelector(SelectSelectorConfig(options=options))}
            ),
        )

    async def _create(self, group_id: str) -> ConfigFlowResult:
        await self.async_set_unique_id(f"{self._user_id}_{group_id}")
        self._abort_if_unique_id_configured()
        name = self._groups.get(group_id, "Eetlijst")
        return self.async_create_entry(
            title=name,
            data={CONF_TOKEN: self._token, CONF_GROUP_ID: group_id, CONF_GROUP_NAME: name},
        )

    # ---- reauth: token expired --------------------------------------------
    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Start reauth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new token."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            errors, api = await self._validate(user_input[CONF_TOKEN])
            if api is not None:
                if f"{api.user_id}_{entry.data[CONF_GROUP_ID]}" != entry.unique_id:
                    errors = {"base": "wrong_account"}
                else:
                    return self.async_update_reload_and_abort(
                        entry, data_updates={CONF_TOKEN: api.token}
                    )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=TOKEN_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Replace the token by hand."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            errors, api = await self._validate(user_input[CONF_TOKEN])
            if api is not None:
                if f"{api.user_id}_{entry.data[CONF_GROUP_ID]}" != entry.unique_id:
                    errors = {"base": "wrong_account"}
                else:
                    return self.async_update_reload_and_abort(
                        entry, data_updates={CONF_TOKEN: api.token}
                    )
        return self.async_show_form(
            step_id="reconfigure", data_schema=TOKEN_SCHEMA, errors=errors
        )
