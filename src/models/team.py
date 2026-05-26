from __future__ import annotations
from typing import Optional
from src.models.pet import Pet

MAX_TEAM_SIZE = 5


class Team:
    def __init__(self):
        self.slots: list[Optional[Pet]] = [None] * MAX_TEAM_SIZE

    # --- queries ---

    @property
    def front(self) -> Optional[Pet]:
        for pet in self.slots:
            if pet and pet.is_alive:
                return pet
        return None

    @property
    def alive_pets(self) -> list[Pet]:
        return [p for p in self.slots if p and p.is_alive]

    @property
    def all_pets(self) -> list[Pet]:
        return [p for p in self.slots if p is not None]

    def is_empty(self) -> bool:
        return self.front is None

    def size(self) -> int:
        return sum(1 for p in self.slots if p is not None)

    def index_of(self, pet: Pet) -> int:
        return self.slots.index(pet)

    def pet_ahead(self, pet: Pet) -> Optional[Pet]:
        idx = self.index_of(pet)
        for i in range(idx - 1, -1, -1):
            if self.slots[i] and self.slots[i].is_alive:
                return self.slots[i]
        return None

    def pet_behind(self, pet: Pet) -> Optional[Pet]:
        idx = self.index_of(pet)
        for i in range(idx + 1, MAX_TEAM_SIZE):
            if self.slots[i] and self.slots[i].is_alive:
                return self.slots[i]
        return None

    # --- mutations ---

    def add_pet(self, pet: Pet, slot: int) -> bool:
        """Place pet at slot. Returns False if slot is occupied."""
        if self.slots[slot] is not None:
            return False
        self.slots[slot] = pet
        return True

    def remove_pet(self, slot: int) -> Optional[Pet]:
        pet = self.slots[slot]
        self.slots[slot] = None
        return pet

    def move_pet(self, from_slot: int, to_slot: int) -> bool:
        if self.slots[from_slot] is None:
            return False
        if self.slots[to_slot] is not None:
            self.slots[from_slot], self.slots[to_slot] = (
                self.slots[to_slot],
                self.slots[from_slot],
            )
        else:
            self.slots[to_slot] = self.slots[from_slot]
            self.slots[from_slot] = None
        return True

    def compact(self):
        """Shift alive pets to the front, remove dead ones."""
        alive = [p for p in self.slots if p and p.is_alive]
        self.slots = alive + [None] * (MAX_TEAM_SIZE - len(alive))

    def summon(self, pet: Pet, after: Pet) -> bool:
        """Insert token immediately after `after` pet. Returns False if team full."""
        if self.size() >= MAX_TEAM_SIZE:
            return False
        idx = self.index_of(after)
        insert_at = idx + 1
        # find first free slot at or after insert_at
        for i in range(insert_at, MAX_TEAM_SIZE):
            if self.slots[i] is None:
                # shift everything between insert_at and i back
                for j in range(i, insert_at, -1):
                    self.slots[j] = self.slots[j - 1]
                self.slots[insert_at] = pet
                return True
        # no free slot after; try inserting before
        for i in range(insert_at - 1, -1, -1):
            if self.slots[i] is None:
                for j in range(i, insert_at - 1):
                    self.slots[j] = self.slots[j + 1]
                self.slots[insert_at - 1] = pet
                return True
        return False

    def first_empty_slot(self) -> Optional[int]:
        for i, p in enumerate(self.slots):
            if p is None:
                return i
        return None

    def clear_temp_buffs(self):
        for pet in self.all_pets:
            pet.clear_temp()

    def reset_alive(self):
        for pet in self.all_pets:
            pet.is_alive = True
            if pet.health <= 0:
                pet.health = 1

    def __repr__(self):
        parts = []
        for i, p in enumerate(self.slots):
            parts.append(f"[{i}] {p}" if p else f"[{i}] empty")
        return "\n".join(parts)
