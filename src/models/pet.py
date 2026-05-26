from __future__ import annotations
from src.models.perk import Perk


class Pet:
    PET_COST = 3
    XP_TO_LEVEL = {1: 2, 2: 3}  # xp needed to reach level 2, then level 3

    def __init__(
        self,
        name: str,
        attack: int,
        health: int,
        tier: int,
        ability: dict,
        is_token: bool = False,
    ):
        self.name = name
        self.attack = attack
        self.health = health
        self.tier = tier
        self.ability = ability
        self.is_token = is_token

        self.temp_attack = 0
        self.temp_health = 0
        self.level = 1
        self.xp = 0
        self.perk: Perk = Perk()
        self.is_alive = True

    @property
    def effective_attack(self) -> int:
        return self.attack + self.temp_attack

    @property
    def effective_health(self) -> int:
        return self.health + self.temp_health

    def take_damage(self, amount: int) -> bool:
        """Apply damage. Returns True if the pet just fainted."""
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.is_alive = False
            return True
        return False

    def buff(self, attack: int = 0, health: int = 0):
        self.attack += attack
        self.health += health

    def temp_buff(self, attack: int = 0, health: int = 0):
        self.temp_attack += attack
        self.temp_health += health

    def clear_temp(self):
        self.temp_attack = 0
        self.temp_health = 0

    def gain_xp(self, amount: int = 1) -> bool:
        """Add xp. Returns True if the pet levelled up."""
        if self.level >= 3:
            return False
        self.xp += amount
        needed = self.XP_TO_LEVEL[self.level]
        if self.xp >= needed:
            self.xp -= needed
            self.level += 1
            return True
        return False

    def ability_scaling(self) -> list[int]:
        """Return [atk_buff, hp_buff] for current level."""
        idx = min(self.level - 1, len(self.ability["scaling"]) - 1)
        return self.ability["scaling"][idx]

    def revive(self):
        self.is_alive = True
        self.health = max(self.health, 1)

    def __repr__(self):
        return (
            f"{self.name.capitalize()}(Lv{self.level} "
            f"{self.effective_attack}/{self.effective_health})"
        )
