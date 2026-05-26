from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Any, Optional
from src.models.pet import Pet

# Priority weights — lower = fires first.
# Follows the canonical order of operations from groundedsap.co.uk
TRIGGER_PRIORITY: dict[str, int] = {
    # Phase markers (handled by battle_engine directly, not queued)
    "before_battle":        0,
    "start_of_battle":      10,
    "before_attack":        20,
    "before_friend_attacks": 21,
    "after_attack":         30,
    "friend_attacks":       31,
    "friend_ahead_attacks": 32,
    "friendly_attacked":    33,
    # Normal order
    "level_up":             40,
    "friend_level_up":      41,
    "hurt":                 50,
    "friend_hurt":          51,
    "enemy_hurt":           52,
    "summoned":             60,
    "friend_summoned":      61,
    "enemy_summoned":       62,
    "faint":                70,
    "friend_ahead_faints":  71,
    "after_faint":          72,
    "friend_faints":        80,
    "enemy_faints":         81,
    "knock_out":            90,
    "transformed":          100,
    "friend_gained_xp":     110,
    "eats_food":            120,
    "sell":                 130,
    "buy":                  140,
    "start_of_turn":        150,
    "end_of_turn":          160,
    "friend_sold":          170,
    "friend_eats_food":     180,
    "friend_gains_xp":      190,
    "none":                 999,
}


@dataclass
class Event:
    trigger: str
    source: Optional[Pet]
    data: dict[str, Any] = field(default_factory=dict)

    def priority(self) -> int:
        return TRIGGER_PRIORITY.get(self.trigger, 500)


class EventQueue:
    def __init__(self):
        self._events: list[Event] = []

    def push(self, event: Event):
        self._events.append(event)

    def push_all(self, events: list[Event]):
        self._events.extend(events)

    def pop_next(self) -> Optional[Event]:
        if not self._events:
            return None
        # Sort by priority, then by descending source attack (highest fires first),
        # randomise ties per groundedsap.co.uk rules.
        self._events.sort(
            key=lambda e: (
                e.priority(),
                -(e.source.effective_attack if e.source else 0),
                random.random(),
            )
        )
        return self._events.pop(0)

    def is_empty(self) -> bool:
        return len(self._events) == 0

    def clear(self):
        self._events.clear()
