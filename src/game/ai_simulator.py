from __future__ import annotations
import random
import copy
import pickle
import os
from src.game.data_loader import GameData
from src.models.team import Team
from src.models.pet import Pet
from src.shop.shop import Shop
from src.engine.ability_engine import AbilityEngine
from src.engine.battle_engine import BattleEngine

STARTING_LIVES = 10
WINS_TO_WIN = 10
MAX_ROUNDS = 30


class AISimulator:
    """
    Runs N random AI games and records each AI's team snapshot at the
    start of every round. These snapshots become the enemy pool.
    """

    def __init__(self, data: GameData):
        self.data = data
        ae = AbilityEngine(game_data=data)
        self.battle_engine = BattleEngine(ae)

    def run_games(self, n: int) -> dict[int, list[Team]]:
        """Returns {round_num: [team_snapshot, ...]}."""
        pool: dict[int, list[Team]] = {}
        for _ in range(n):
            self._run_one_game(pool)
        return pool

    def _run_one_game(self, pool: dict[int, list[Team]]):
        team = Team()
        lives = STARTING_LIVES
        wins = 0
        round_num = 1

        while lives > 0 and wins < WINS_TO_WIN and round_num <= MAX_ROUNDS:
            # Shop phase: random decisions
            shop = Shop(round_num=round_num, data=self.data)
            gold = 10
            gold = self._random_shop_phase(shop, team, gold)

            # Snapshot AFTER shop (this is the team opponents fight)
            snapshot = copy.deepcopy(team)
            pool.setdefault(round_num, []).append(snapshot)

            # Generate random enemy and battle
            enemy = self._random_enemy(round_num)
            result = self.battle_engine.run(team, enemy)

            if result.winner == "player":
                wins += 1
            elif result.winner == "enemy":
                lives -= 1

            # Reset team for next round
            team.clear_temp_buffs()
            team.reset_alive()
            round_num += 1

    def _random_shop_phase(self, shop: Shop, team: Team, gold: int) -> int:
        # Try to buy pets while we can afford it
        attempts = 0
        while gold >= Shop.PET_COST and attempts < 20:
            attempts += 1
            # Find available slots
            available = [i for i, s in enumerate(shop.pet_slots) if not s.is_empty()]
            if not available:
                break
            idx = random.choice(available)
            ok, _, gold = shop.buy_pet(idx, team, gold)

        # 25% chance to buy food if we can
        if gold >= Shop.FOOD_COST and random.random() < 0.25:
            avail_food = [i for i, s in enumerate(shop.food_slots) if not s.is_empty()]
            if avail_food and team.alive_pets:
                fi = random.choice(avail_food)
                ti = random.randrange(5)
                shop.buy_food(fi, team, gold, target_slot=ti)

        # 20% chance to reroll once
        if gold >= Shop.REROLL_COST and random.random() < 0.2:
            ok, _, gold = shop.reroll(gold)
            # Try buying again after reroll
            available = [i for i, s in enumerate(shop.pet_slots) if not s.is_empty()]
            if available and gold >= Shop.PET_COST:
                idx = random.choice(available)
                shop.buy_pet(idx, team, gold)

        return gold

    def _random_enemy(self, round_num: int) -> Team:
        from src.models.team import MAX_TEAM_SIZE
        tier = min(1 + round_num // 3, 6)
        pool = self.data.pets_by_tier(tier)
        team = Team()
        n = min(round_num, MAX_TEAM_SIZE)
        names = random.choices(pool, k=n)
        for i, name in enumerate(names):
            pet = self.data.make_pet(name)
            bonus = round_num // 3
            pet.buff(bonus, bonus)
            team.add_pet(pet, i)
        return team
