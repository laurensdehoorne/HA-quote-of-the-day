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
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    CONF_AI_INSTRUCTIONS,
    CONF_AI_TASK_ENTITY,
    CONF_CACHE_DAYS,
    CONF_LANGUAGE,
    CONF_ON_THIS_DAY,
    CONF_SOURCES,
    CONF_THEME,
    DEFAULT_CACHE_DAYS,
    DEFAULT_LANGUAGE,
    DEFAULT_ON_THIS_DAY,
    DEFAULT_SOURCES,
    DEFAULT_THEME,
    DOMAIN,
    LANGUAGES,
    MAX_CACHE_DAYS,
    MIN_CACHE_DAYS,
    SOURCES,
    THEMES,
)


def _schema(values: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_THEME, default=values.get(CONF_THEME, DEFAULT_THEME)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=THEMES,
                    translation_key=CONF_THEME,
                    mode=SelectSelectorMode.LIST,
                )
            ),
            vol.Required(
                CONF_SOURCES, default=values.get(CONF_SOURCES, DEFAULT_SOURCES)
            ): vol.All(
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
            vol.Required(
                CONF_LANGUAGE, default=values.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=LANGUAGES,
                    translation_key=CONF_LANGUAGE,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_CACHE_DAYS, default=values.get(CONF_CACHE_DAYS, DEFAULT_CACHE_DAYS)
            ): vol.All(
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
            vol.Required(
                CONF_ON_THIS_DAY, default=values.get(CONF_ON_THIS_DAY, DEFAULT_ON_THIS_DAY)
            ): BooleanSelector(),
            # Optional: without an AI Task entity there is no AI quote.
            vol.Optional(
                CONF_AI_TASK_ENTITY,
                description={"suggested_value": values.get(CONF_AI_TASK_ENTITY) or None},
            ): EntitySelector(EntitySelectorConfig(domain="ai_task")),
            vol.Optional(
                CONF_AI_INSTRUCTIONS,
                description={"suggested_value": values.get(CONF_AI_INSTRUCTIONS) or None},
            ): TextSelector(TextSelectorConfig(multiline=True)),
        }
    )


def _with_cleared_fields(user_input: dict[str, Any]) -> dict[str, Any]:
    """Store emptied optional fields too, so they override the setup values."""
    return {CONF_AI_TASK_ENTITY: "", CONF_AI_INSTRUCTIONS: "", **user_input}


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
            data_schema=_schema({}),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return QuoteOfTheDayOptionsFlow()


class QuoteOfTheDayOptionsFlow(OptionsFlow):
    """Change the settings after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=_with_cleared_fields(user_input))

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(current),
        )
