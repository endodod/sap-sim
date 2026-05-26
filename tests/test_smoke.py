"""
Phase 1 regression tests.

Smoke test: 100 AI games, assert mean team stats at round 5 exceed the
baseline produced by the broken (no-events) simulator.

Calibration:
  broken simulator (no shop-phase events): mean ~18.3
  fixed simulator  (all events firing):    mean ~21.2
  threshold: 20  — sits clearly between the two
"""
import pytest
from src.game.data_loader import DataLoader
from src.game.ai_simulator import AISimulator
from src.engine.battle_engine import BattleResult
from src.engine.event_queue import Event, EventQueue
from src.engine.ability_engine import AbilityEngine
from src.models.team import Team
from src.shop.shop import Shop

N_GAMES = 100
ROUND = 5
MEAN_STATS_THRESHOLD = 20  # broken ~18.3, fixed ~21.2


# ---------------------------------------------------------------------------
# 100-game smoke test
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def game_data():
    return DataLoader().load()


@pytest.fixture(scope="module")
def round5_pool(game_data):
    sim = AISimulator(game_data)
    pool = sim.run_games(N_GAMES)
    return pool.get(ROUND, [])


def test_round5_has_enough_snapshots(round5_pool):
    assert len(round5_pool) >= N_GAMES * 0.9, (
        f"Expected ~{N_GAMES} round-5 snapshots, got {len(round5_pool)}"
    )


def test_mean_team_stats_above_threshold(round5_pool):
    """Fails if shop-phase events (buy, end_of_turn, on_level_up) stop firing."""
    stats = [sum(p.attack + p.health for p in t.alive_pets) for t in round5_pool]
    mean = sum(stats) / len(stats)
    assert mean >= MEAN_STATS_THRESHOLD, (
        f"Mean team stats at round {ROUND} = {mean:.1f}, "
        f"expected >= {MEAN_STATS_THRESHOLD}. "
        f"Shop-phase events may not be firing correctly."
    )


def test_teams_have_pets(round5_pool):
    empty = [t for t in round5_pool if not t.alive_pets]
    assert not empty, f"{len(empty)} round-5 teams have no living pets"


# ---------------------------------------------------------------------------
# training_label: draw → loss
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("winner,expected", [
    ("player", "win"),
    ("enemy",  "loss"),
    ("draw",   "loss"),
])
def test_training_label(winner, expected):
    r = BattleResult(winner=winner, player_survivors=0, enemy_survivors=0, log=[])
    assert r.training_label == expected


# ---------------------------------------------------------------------------
# Cow: buy fires add-Milk-to-shop
# ---------------------------------------------------------------------------

def test_cow_buy_adds_milk_to_shop(game_data):
    ae = AbilityEngine(game_data=game_data)
    team = Team()
    cow = game_data.make_pet("cow")
    team.add_pet(cow, 0)

    shop = Shop(round_num=9, data=game_data)  # tier 5 so Milk is legal
    # Ensure food slots start empty
    for slot in shop.food_slots:
        slot.item = None

    queue = EventQueue()
    queue.push(Event(trigger="buy", source=cow, data={"shop": shop}))
    log: list[str] = []
    ae.process_queue(queue, team, Team(), log)

    food_names = [s.item.name for s in shop.food_slots if s.item is not None]
    assert "milk" in food_names, f"Expected Milk in shop food slots, got: {food_names}"


# ---------------------------------------------------------------------------
# Otter buy event fires (buy trigger gives +1/+1 to a random friend)
# ---------------------------------------------------------------------------

def test_otter_buy_event_buffs_friend(game_data):
    ae = AbilityEngine(game_data=game_data)
    team = Team()
    otter = game_data.make_pet("otter")
    friend = game_data.make_pet("ant")
    team.add_pet(otter, 0)
    team.add_pet(friend, 1)

    before = friend.attack + friend.health

    queue = EventQueue()
    queue.push(Event(trigger="buy", source=otter, data={}))
    log: list[str] = []
    ae.process_queue(queue, team, Team(), log)

    after = friend.attack + friend.health
    assert after > before, "Otter buy event should buff a random friend"


# ---------------------------------------------------------------------------
# end_of_turn: Giraffe buffs friends ahead
# ---------------------------------------------------------------------------

def test_giraffe_end_of_turn_buffs(game_data):
    ae = AbilityEngine(game_data=game_data)
    team = Team()
    front = game_data.make_pet("ant")
    giraffe = game_data.make_pet("giraffe")
    team.add_pet(front, 0)    # slot 0: ahead
    team.add_pet(giraffe, 1)  # slot 1: giraffe fires end_of_turn

    before = front.attack + front.health

    queue = EventQueue()
    queue.push_all(ae.emit_for_all("end_of_turn", team))
    log: list[str] = []
    ae.process_queue(queue, team, Team(), log)

    after = front.attack + front.health
    assert after > before, "Giraffe end_of_turn should buff friends ahead"


# ---------------------------------------------------------------------------
# Dragon / on_level_up: friend_gains_xp gives all friends +1/+1
# ---------------------------------------------------------------------------

def test_dragon_fires_on_level_up(game_data):
    ae = AbilityEngine(game_data=game_data)
    team = Team()
    dragon = game_data.make_pet("dragon")
    fish = game_data.make_pet("fish")
    levelling_pet = game_data.make_pet("ant")
    team.add_pet(dragon, 0)
    team.add_pet(fish, 1)
    team.add_pet(levelling_pet, 2)

    before_fish = fish.attack + fish.health

    # Simulate on_level_up callback
    queue = EventQueue()
    queue.push(Event(trigger="level_up", source=levelling_pet, data={}))
    for other in team.alive_pets:
        if other is not levelling_pet and other.ability.get("trigger") == "friend_gains_xp":
            queue.push(Event(trigger="friend_gains_xp", source=other, data={}))
    log: list[str] = []
    ae.process_queue(queue, team, Team(), log)

    after_fish = fish.attack + fish.health
    assert after_fish > before_fish, "Dragon friend_gains_xp should buff all friends"
