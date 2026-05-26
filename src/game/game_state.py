from __future__ import annotations
import random
from src.game.data_loader import GameData
from src.models.team import Team
from src.shop.shop import Shop
from src.engine.ability_engine import AbilityEngine
from src.engine.battle_engine import BattleEngine
from src.engine.event_queue import Event, EventQueue

STARTING_LIVES = 10
GOLD_PER_TURN = 10
WINS_TO_WIN = 10


class GameState:
    def __init__(self, data: GameData, enemy_pool=None):
        self.data = data
        self.player_team = Team()
        self.round = 1
        self.lives = STARTING_LIVES
        self.wins = 0
        self.gold = GOLD_PER_TURN
        self.shop: Shop = self._new_shop()
        self.win_streak = 0
        self.loss_streak = 0

        self.ability_engine = AbilityEngine(game_data=data)
        self.battle_engine = BattleEngine(self.ability_engine)
        self.enemy_pool = enemy_pool  # EnemyPool | None

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def start_turn(self):
        self.gold = GOLD_PER_TURN + self._streak_bonus()
        self.shop = self._new_shop()
        self.player_team.clear_temp_buffs()
        self.player_team.reset_alive()
        for pet in self.player_team.all_pets:
            pet.perk.reset()
            pet._perk_used_this_round = False
        self._fire_start_of_turn_events()

    def end_turn(self) -> dict:
        self._fire_end_of_turn_events()
        enemy_team = self._generate_enemy()
        result = self.battle_engine.run(self.player_team, enemy_team)

        if result.winner == "player":
            self.wins += 1
            self.win_streak += 1
            self.loss_streak = 0
        elif result.winner == "enemy":
            self.lives -= 1
            self.loss_streak += 1
            self.win_streak = 0
        else:
            self.win_streak = 0
            self.loss_streak = 0

        self.round += 1
        return {
            "result": result,
            "lives": self.lives,
            "wins": self.wins,
            "game_over": self.lives <= 0,
            "victory": self.wins >= WINS_TO_WIN,
        }

    def is_over(self) -> bool:
        return self.lives <= 0 or self.wins >= WINS_TO_WIN

    # ------------------------------------------------------------------
    # Shop actions
    # ------------------------------------------------------------------

    def buy_pet(self, shop_idx: int, team_slot: int | None = None) -> tuple[bool, str]:
        if team_slot is not None:
            ok, msg, self.gold = self.shop.buy_pet_to_slot(shop_idx, team_slot, self.player_team, self.gold)
        else:
            ok, msg, self.gold = self.shop.buy_pet(shop_idx, self.player_team, self.gold)
        if ok:
            # find the pet that was just placed (most recently added non-None)
            bought_pet = self._last_added_pet()
            if bought_pet:
                self._fire_shop_event("buy", bought_pet, shop=self.shop)
                # notify existing pets of friend_summoned
                for pet in self.player_team.alive_pets:
                    if pet is not bought_pet and pet.ability.get("trigger") == "friend_summoned":
                        self._fire_shop_event_for_pet("friend_summoned", pet,
                                                       data={"summoned_pet": bought_pet})
        return ok, msg

    def sell_pet(self, team_slot: int) -> tuple[bool, str]:
        pet = self.player_team.slots[team_slot]
        if pet:
            bonus = self.shop.get_sell_gold_bonus(pet)
            self.gold += bonus
            # Fire sell trigger before removing
            self._fire_shop_event("sell", pet, shop=self.shop)
            # Notify shrimp and similar
            for other in self.player_team.alive_pets:
                if other is not pet and other.ability.get("trigger") == "friend_sold":
                    self._fire_shop_event_for_pet("friend_sold", other)
        ok, msg, self.gold = self.shop.sell_pet(team_slot, self.player_team, self.gold)
        return ok, msg

    def buy_food(self, shop_idx: int, target_slot: int | None = None) -> tuple[bool, str]:
        # Check for cat in team (multiplies food buff)
        cat_multiplier = 1
        for pet in self.player_team.alive_pets:
            if pet.name == "cat":
                cat_multiplier = pet.ability_scaling()[0]
                break

        ok, msg, self.gold = self.shop.buy_food(
            shop_idx, self.player_team, self.gold, target_slot,
            food_multiplier=cat_multiplier,
        )
        if ok and target_slot is not None:
            target = self.player_team.slots[target_slot]
            if target:
                # Notify rabbit
                for pet in self.player_team.alive_pets:
                    if pet is not target and pet.ability.get("trigger") == "friend_eats_food":
                        self._fire_shop_event_for_pet("friend_eats_food", pet,
                                                       data={"eating_pet": target})
                # Notify dragon
                self._fire_shop_event("eats_food", target)
        return ok, msg

    def reroll(self) -> tuple[bool, str]:
        ok, msg, self.gold = self.shop.reroll(self.gold)
        return ok, msg

    def freeze(self, index: int, is_food: bool = False) -> tuple[bool, str]:
        return self.shop.freeze(index, is_food)

    def move_pet(self, from_slot: int, to_slot: int) -> tuple[bool, str]:
        return self.shop.move_pet(from_slot, to_slot, self.player_team)

    # ------------------------------------------------------------------
    # Shop-phase event firing
    # ------------------------------------------------------------------

    def _fire_shop_event(self, trigger: str, source_pet, shop=None, data: dict | None = None):
        dummy_enemy = Team()
        queue = EventQueue()
        evt_data = data or {}
        if shop:
            evt_data = {**evt_data, "shop": shop}
        queue.push(Event(trigger=trigger, source=source_pet, data=evt_data))
        log: list[str] = []
        self.ability_engine.process_queue(queue, self.player_team, dummy_enemy, log)

    def _fire_shop_event_for_pet(self, trigger: str, pet, data: dict | None = None):
        dummy_enemy = Team()
        queue = EventQueue()
        queue.push(Event(trigger=trigger, source=pet, data=data or {}))
        log: list[str] = []
        self.ability_engine.process_queue(queue, self.player_team, dummy_enemy, log)

    def _fire_start_of_turn_events(self):
        dummy_enemy = Team()
        queue = EventQueue()
        queue.push_all(self.ability_engine.emit_for_all("start_of_turn", self.player_team))
        log: list[str] = []
        self.ability_engine.process_queue(queue, self.player_team, dummy_enemy, log)
        # Swan gives gold
        for pet in self.player_team.alive_pets:
            if pet.ability.get("trigger") == "start_of_turn" and pet.ability.get("effect") == "gain_gold":
                atk, _ = pet.ability_scaling()
                self.gold += atk

    def _fire_end_of_turn_events(self):
        dummy_enemy = Team()
        queue = EventQueue()
        queue.push_all(self.ability_engine.emit_for_all("end_of_turn", self.player_team))
        log: list[str] = []
        self.ability_engine.process_queue(queue, self.player_team, dummy_enemy, log)

    # ------------------------------------------------------------------
    # Level-up notification (called by shop when combine happens)
    # ------------------------------------------------------------------

    def notify_level_up(self, pet):
        self._fire_shop_event("level_up", pet)
        # Dragon and similar react to friend gaining XP
        for other in self.player_team.alive_pets:
            if other is not pet and other.ability.get("trigger") == "friend_gains_xp":
                self._fire_shop_event_for_pet("friend_gains_xp", other)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _last_added_pet(self):
        for pet in reversed(self.player_team.slots):
            if pet:
                return pet
        return None

    def _streak_bonus(self) -> int:
        streak = max(self.win_streak, self.loss_streak)
        if streak >= 3:
            return 2
        if streak >= 2:
            return 1
        return 0

    def _new_shop(self) -> Shop:
        return Shop(round_num=self.round, data=self.data, on_level_up=self.notify_level_up)

    def _generate_enemy(self) -> Team:
        if self.enemy_pool:
            return self.enemy_pool.get_enemy(self.round)
        return self._random_enemy()

    def _random_enemy(self) -> Team:
        from src.models.team import MAX_TEAM_SIZE
        tier = min(1 + self.round // 3, 6)
        pool = self.data.pets_by_tier(tier)
        team = Team()
        n = min(self.round, MAX_TEAM_SIZE)
        names = random.choices(pool, k=n)
        for i, name in enumerate(names):
            pet = self.data.make_pet(name)
            bonus = self.round // 3
            pet.buff(bonus, bonus)
            team.add_pet(pet, i)
        return team
