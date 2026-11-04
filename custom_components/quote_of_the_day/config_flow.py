"""Config flow for Quote of the Day."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_CACHE_DAYS,
    CONF_LANGUAGE,
    CONF_ON_THIS_DAY,
    CONF_SOURCES,
    DEFAULT_CACHE_DAYS,
    DEFAULT_LANGUAGE,
    DEFAULT_ON_THIS_DAY,
    DEFAULT_SOURCES,
    DOMAIN,
    LANGUAGES,
    MAX_CACHE_DAYS,
    MIN_CACHE_DAYS,
    SOURCES,
)


def _schema(
    sources: list[str], language: str, cache_days: int, on_this_day: bool
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_SOURCES, default=sources): vol.All(
                SelectSelector(
                    SelectSelectorConfig(
                        options=SOURCES,
                        translation_key=CONF_SOURCES,
                        mode=SelectSelectorMode.LIST,
                        multiple=True,
                    )
                ),
                vol.Length(min=1),
            ),
            vol.Required(CONF_LANGUAGE, default=language): SelectSelector(
                SelectSelectorConfig(
                    options=LANGUAGES,
                    translation_key=CONF_LANGUAGE,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_CACHE_DAYS, default=cache_days): vol.All(
                NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_CACHE_DAYS,
                        max=MAX_CACHE_DAYS,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="days",
                    )
                ),
                vol.Coerce(int),
            ),
            vol.Required(CONF_ON_THIS_DAY, default=on_this_day): BooleanSelector(),
        }
    )


class QuoteOfTheDayConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flow."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Quote of the Day", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(
                DEFAULT_SOURCES, DEFAULT_LANGUAGE, DEFAULT_CACHE_DAYS, DEFAULT_ON_THIS_DAY
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return QuoteOfTheDayOptionsFlow()


class QuoteOfTheDayOptionsFlow(OptionsFlow):
    """Change source and language after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(
                current.get(CONF_SOURCES, DEFAULT_SOURCES),
                current.get(CONF_LANGUAGE, DEFAULT_LANGUAGE),
                current.get(CONF_CACHE_DAYS, DEFAULT_CACHE_DAYS),
                current.get(CONF_ON_THIS_DAY, DEFAULT_ON_THIS_DAY),
            ),
        )
