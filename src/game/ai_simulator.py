from __future__ import annotations
import random
import copy
from src.game.data_loader import GameData
from src.models.team import Team
from src.models.pet import Pet
from src.shop.shop import Shop
from src.engine.ability_engine import AbilityEngine
from src.engine.battle_engine import BattleEngine
from src.engine.event_queue import Event, EventQueue

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
        self.ability_engine = AbilityEngine(game_data=data)
        self.battle_engine = BattleEngine(self.ability_engine)

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
            # Shop phase: random decisions with correct event firing
            on_level_up = self._make_on_level_up(team)
            shop = Shop(round_num=round_num, data=self.data, on_level_up=on_level_up)
            gold = 10
            gold = self._random_shop_phase(shop, team, gold)

            # Fire end_of_turn before battle (Giraffe, Monkey, Penguin, Bison)
            self._fire_end_of_turn(team)

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
        attempts = 0
        while gold >= Shop.PET_COST and attempts < 20:
            attempts += 1
            available = [i for i, s in enumerate(shop.pet_slots) if not s.is_empty()]
            if not available:
                break
            idx = random.choice(available)
            ok, _, gold = shop.buy_pet(idx, team, gold)
            if ok:
                self._fire_buy_events(shop, team)

        if gold >= Shop.FOOD_COST and random.random() < 0.25:
            avail_food = [i for i, s in enumerate(shop.food_slots) if not s.is_empty()]
            if avail_food and team.alive_pets:
                fi = random.choice(avail_food)
                ti = random.randrange(5)
                shop.buy_food(fi, team, gold, target_slot=ti)

        if gold >= Shop.REROLL_COST and random.random() < 0.2:
            ok, _, gold = shop.reroll(gold)
            available = [i for i, s in enumerate(shop.pet_slots) if not s.is_empty()]
            if available and gold >= Shop.PET_COST:
                idx = random.choice(available)
                ok2, _, gold = shop.buy_pet(idx, team, gold)
                if ok2:
                    self._fire_buy_events(shop, team)

        return gold

    # ------------------------------------------------------------------
    # Shop-phase event helpers (mirrors game_state logic)
    # ------------------------------------------------------------------

    def _fire_buy_events(self, shop: Shop, team: Team):
        bought_pet = _last_added_pet(team)
        if not bought_pet:
            return
        dummy_enemy = Team()
        queue = EventQueue()
        queue.push(Event(trigger="buy", source=bought_pet, data={"shop": shop}))
        for pet in team.alive_pets:
            if pet is not bought_pet and pet.ability.get("trigger") == "friend_summoned":
                queue.push(Event(trigger="friend_summoned", source=pet,
                                 data={"summoned_pet": bought_pet}))
        log: list[str] = []
        self.ability_engine.process_queue(queue, team, dummy_enemy, log)

    def _fire_end_of_turn(self, team: Team):
        dummy_enemy = Team()
        queue = EventQueue()
        queue.push_all(self.ability_engine.emit_for_all("end_of_turn", team))
        log: list[str] = []
        self.ability_engine.process_queue(queue, team, dummy_enemy, log)

    def _make_on_level_up(self, team: Team):
        def on_level_up(pet: Pet):
            dummy_enemy = Team()
            queue = EventQueue()
            queue.push(Event(trigger="level_up", source=pet, data={}))
            for other in team.alive_pets:
                if other is not pet and other.ability.get("trigger") == "friend_gains_xp":
                    queue.push(Event(trigger="friend_gains_xp", source=other, data={}))
            log: list[str] = []
            self.ability_engine.process_queue(queue, team, dummy_enemy, log)
        return on_level_up

    # ------------------------------------------------------------------

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


def _last_added_pet(team: Team) -> Pet | None:
    for pet in reversed(team.slots):
        if pet:
            return pet
    return None
