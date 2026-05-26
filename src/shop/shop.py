from __future__ import annotations
import random
from typing import Optional, Callable
from src.models.pet import Pet
from src.models.food import Food
from src.models.team import Team
from src.game.data_loader import GameData


def _shop_config(round_num: int) -> tuple[int, int]:
    if round_num <= 2:   return 3, 1
    elif round_num <= 4: return 4, 1
    elif round_num <= 7: return 4, 2
    else:                return 5, 2


def _max_tier(round_num: int) -> int:
    if round_num <= 2:  return 1
    if round_num <= 4:  return 2
    if round_num <= 6:  return 3
    if round_num <= 8:  return 4
    if round_num <= 10: return 5
    return 6


class ShopSlot:
    def __init__(self, item: Pet | Food | None = None):
        self.item = item
        self.frozen = False

    def is_empty(self) -> bool:
        return self.item is None


class Shop:
    PET_COST = 3
    FOOD_COST = 3
    REROLL_COST = 1

    def __init__(self, round_num: int, data: GameData,
                 on_level_up: Callable[[Pet], None] | None = None):
        self.round_num = round_num
        self.data = data
        self.tier = _max_tier(round_num)
        self.on_level_up = on_level_up  # callback → game_state.notify_level_up
        # Persistent shop buff from canned_food
        self.shop_atk_buff = 0
        self.shop_hp_buff = 0

        n_pets, n_foods = _shop_config(round_num)
        self.pet_slots: list[ShopSlot] = [ShopSlot() for _ in range(n_pets)]
        self.food_slots: list[ShopSlot] = [ShopSlot() for _ in range(n_foods)]
        self._fill()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _fill(self):
        pool = self.data.pets_by_tier(self.tier)
        food_pool = self.data.foods_by_tier(self.tier)
        for slot in self.pet_slots:
            if not slot.frozen:
                if pool:
                    pet = self.data.make_pet(random.choice(pool))
                    pet.buff(self.shop_atk_buff, self.shop_hp_buff)
                    slot.item = pet
                else:
                    slot.item = None
        for slot in self.food_slots:
            if not slot.frozen:
                slot.item = self.data.make_food(random.choice(food_pool)) if food_pool else None
        # 1-in-10000 chance: replace leftmost unfrozen pet slot with the Sloth
        if random.randint(1, 10000) == 1:
            for slot in self.pet_slots:
                if not slot.frozen:
                    slot.item = self.data.make_pet("sloth")
                    break

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def reroll(self, gold: int) -> tuple[bool, str, int]:
        if gold < self.REROLL_COST:
            return False, "Not enough gold to reroll.", gold
        gold -= self.REROLL_COST
        self._fill()
        return True, "Shop rerolled.", gold

    def freeze(self, index: int, is_food: bool = False) -> tuple[bool, str]:
        slots = self.food_slots if is_food else self.pet_slots
        if index < 0 or index >= len(slots):
            return False, "Invalid slot."
        slots[index].frozen = not slots[index].frozen
        state = "frozen" if slots[index].frozen else "unfrozen"
        return True, f"Slot {index} {state}."

    def buy_pet(self, shop_index: int, team: Team, gold: int) -> tuple[bool, str, int]:
        if shop_index < 0 or shop_index >= len(self.pet_slots):
            return False, "Invalid shop slot.", gold
        slot = self.pet_slots[shop_index]
        if slot.is_empty():
            return False, "That shop slot is empty.", gold
        if gold < self.PET_COST:
            return False, "Not enough gold.", gold

        pet: Pet = slot.item

        # Combine: 3 copies → level up
        same = [p for p in team.all_pets if p.name == pet.name]
        if len(same) >= 2:
            base = same[0]
            base.attack = max(base.attack, pet.attack)
            base.health = max(base.health, pet.health)
            levelled_up = base.gain_xp(1)
            slot.item = None
            gold -= self.PET_COST
            if levelled_up and self.on_level_up:
                self.on_level_up(base)
            if levelled_up:
                return True, f"{pet.name} levelled up to Lv{base.level}!", gold
            return True, f"{pet.name} combined ({base.xp}/{base.XP_TO_LEVEL.get(base.level, '?')} xp).", gold

        free = team.first_empty_slot()
        if free is None:
            return False, "Team is full. Sell a pet first.", gold
        team.add_pet(pet, free)
        slot.item = None
        gold -= self.PET_COST
        return True, f"Bought {pet.name}.", gold

    def buy_pet_to_slot(self, shop_index: int, team_slot: int, team: Team, gold: int) -> tuple[bool, str, int]:
        if shop_index < 0 or shop_index >= len(self.pet_slots):
            return False, "Invalid shop slot.", gold
        slot = self.pet_slots[shop_index]
        if slot.is_empty():
            return False, "That shop slot is empty.", gold
        if gold < self.PET_COST:
            return False, "Not enough gold.", gold
        if team_slot < 0 or team_slot >= 5:
            return False, "Invalid team slot.", gold

        pet: Pet = slot.item
        same = [p for p in team.all_pets if p.name == pet.name]
        if len(same) >= 2:
            return self.buy_pet(shop_index, team, gold)

        if team.slots[team_slot] is not None:
            return False, f"Team slot {team_slot} is occupied.", gold
        team.add_pet(pet, team_slot)
        slot.item = None
        gold -= self.PET_COST
        return True, f"Bought {pet.name} into slot {team_slot}.", gold

    def sell_pet(self, team_slot: int, team: Team, gold: int) -> tuple[bool, str, int]:
        if team_slot < 0 or team_slot >= 5:
            return False, "Invalid slot.", gold
        pet = team.slots[team_slot]
        if pet is None:
            return False, "No pet in that slot.", gold
        team.remove_pet(team_slot)
        gold += 1
        return True, f"Sold {pet.name} for 1 gold.", gold

    def buy_food(self, shop_index: int, team: Team, gold: int,
                 target_slot: Optional[int] = None,
                 food_multiplier: int = 1) -> tuple[bool, str, int]:
        if shop_index < 0 or shop_index >= len(self.food_slots):
            return False, "Invalid food slot.", gold
        slot = self.food_slots[shop_index]
        if slot.is_empty():
            return False, "That food slot is empty.", gold
        food: Food = slot.item
        if gold < food.cost:
            return False, "Not enough gold.", gold

        effect = food.ability.get("effect", "none")
        target_type = food.ability.get("target", "none")
        scaling = food.ability.get("scaling", [[0, 0]])[0]
        atk_buff = scaling[0] * food_multiplier
        hp_buff  = scaling[1] * food_multiplier
        msg = ""

        if target_type == "chosen_friend":
            if target_slot is None:
                return False, f"Specify a team slot for {food.name}.", gold
            pet = team.slots[target_slot]
            if pet is None:
                return False, "No pet in that slot.", gold
            if "temp" in effect:
                pet.temp_buff(atk_buff, hp_buff)
            else:
                pet.buff(atk_buff, hp_buff)
            msg = f"{food.name} gave {pet.name} +{atk_buff}/+{hp_buff}."

        elif target_type == "two_random_friends":
            targets = random.sample(team.alive_pets, min(2, len(team.alive_pets)))
            for t in targets:
                if "temp" in effect:
                    t.temp_buff(atk_buff, hp_buff)
                else:
                    t.buff(atk_buff, hp_buff)
            msg = f"{food.name} buffed {', '.join(t.name for t in targets)}."

        elif target_type == "three_random_friends":
            targets = random.sample(team.alive_pets, min(3, len(team.alive_pets)))
            for t in targets:
                t.buff(atk_buff, hp_buff)
            msg = f"{food.name} buffed {', '.join(t.name for t in targets)}."

        elif effect == "give_perk":
            if target_slot is None:
                return False, f"Specify a team slot for {food.name}.", gold
            pet = team.slots[target_slot]
            if pet is None:
                return False, "No pet in that slot.", gold
            from src.models.perk import Perk
            perk_name = food.ability.get("perk", "none")
            pet.perk = Perk(name=perk_name, effect=perk_name)
            msg = f"{pet.name} got perk: {perk_name}."

        elif effect == "faint_target":
            if target_slot is None:
                return False, f"Specify a team slot for {food.name}.", gold
            pet = team.slots[target_slot]
            if pet is None:
                return False, "No pet in that slot.", gold
            pet.is_alive = False
            msg = f"{pet.name} fainted (pill)."

        elif effect == "give_all_future_shop_pets_stats":
            self.shop_atk_buff += atk_buff
            self.shop_hp_buff += hp_buff
            msg = f"Canned food: all future shop pets +{atk_buff}/+{hp_buff} permanently."

        elif effect == "give_target_random_perk":
            if target_slot is None:
                return False, f"Specify a team slot for {food.name}.", gold
            pet = team.slots[target_slot]
            if pet is None:
                return False, "No pet in that slot.", gold
            from src.models.perk import Perk
            perks = ["bone_attack", "melon_armor", "coconut_shield"]
            chosen = random.choice(perks)
            pet.perk = Perk(name=chosen, effect=chosen)
            msg = f"{pet.name} got random perk: {chosen}."

        else:
            msg = f"Used {food.name}."

        slot.item = None
        gold -= food.cost
        return True, msg, gold

    def move_pet(self, from_slot: int, to_slot: int, team: Team) -> tuple[bool, str]:
        ok = team.move_pet(from_slot, to_slot)
        if ok:
            return True, f"Moved slot {from_slot} <-> {to_slot}."
        return False, "Cannot move: invalid slot or no pet there."

    def get_sell_gold_bonus(self, pet: Pet) -> int:
        if pet.ability.get("trigger") == "sell" and pet.ability.get("effect") == "gain_gold":
            atk, _ = pet.ability_scaling()
            return atk
        return 0
