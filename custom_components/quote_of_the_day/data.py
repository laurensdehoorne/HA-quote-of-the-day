"""Runtime data shared by the platforms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .ai_coordinator import AiQuoteCoordinator
    from .coordinator import QuoteCoordinator
    from .onthisday_coordinator import OnThisDayCoordinator


@dataclass(slots=True)
class QuoteRuntimeData:
    """Coordinators of a config entry."""

    quotes: QuoteCoordinator
    on_this_day: OnThisDayCoordinator | None
    ai_quote: AiQuoteCoordinator | None = None


type QuoteConfigEntry = ConfigEntry[QuoteRuntimeData]
