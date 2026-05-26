# Handshake — Simulation State for AI Training

This document describes what is fully implemented, what is known to be missing,
and the exact problem with the enemy pool. Read this before building any training
loop on top of this codebase.

---

## What is complete and reliable

### Battle engine (`src/engine/`)
- All 30 Pack-1 pets are registered with working ability handlers.
- Battle phases fire in the correct order:
  `start_of_battle → before_attack → attack → hurt/faint/knock_out/friend_faints → after_attack → friend_ahead_attacks`
- Simultaneous death is handled; both faint chains resolve before compaction.
- Perk system works: `bone_attack`, `melon_armor`, `coconut_shield`, `poisoned_attack`.
- Token chains work: Cricket spawns Zombie Cricket; Fly spawns Zombie Fly (capped at 3).
- Whale swallow/release works (including the bug fix: events queued for a pet that gets
  swallowed before its event fires are now silently dropped in `_dispatch`).
- Max 50 turns enforced; draw declared when both sides survive.
- Event queue sorts by trigger priority → descending attack → random tie-break,
  matching the canonical order from groundedsap.co.uk.

### Shop (`src/shop/shop.py`)
- Tier unlocks, shop size, reroll, freeze, buy, sell all work correctly.
- Combine/level-up: 3 copies → Lv2 (2 XP), 6 copies → Lv3 (2+3 XP).
- All 12 food items from Foods.yaml are implemented and apply correct effects.
- Sell gold: 1g base; Pig adds +1g, Swan adds +1g per level on sell.
- Sloth: secret pet, never in normal pool; appears in leftmost unfrozen slot
  with probability 1/10000 per fill (initial open + every reroll).
- Shop-phase ability triggers fire for the player via `GameState` callbacks
  (`buy`, `friend_summoned`, `friend_eats_food`).

### Game loop (`src/game/game_state.py`)
- 10 lives, 10-win target, rounds 1–15+.
- Gold per round: 10 base + streak bonus (+1g at streak ≥ 2, +2g at streak ≥ 3).
- Win/loss streaks tracked separately; bonus uses whichever is active.
- Round advancement creates a new `Shop` instance with correct tier for that round.

---

## Known gaps (not implemented)

| # | What | Where | Status |
|---|------|--------|--------|
| 1 | `end_of_turn` events never fire | No call site in shop phase | **Fixed** — `game_state.end_turn()` fires `_fire_end_of_turn_events()`; AI loop calls `_fire_end_of_turn()` before battle |
| 2 | `buy` / `friend_summoned` events not fired in AI games | `ai_simulator.py` | **Fixed** — `_fire_buy_events()` fires after every `shop.buy_pet()` success |
| 3 | Cow "add Milk to shop" stub | `ability_engine.py` | **Fixed** — handler places a real Milk food item in the first empty food slot |
| 4 | Draw outcome for training labels | `battle_engine.py` returns `"draw"` | **Fixed** — `BattleResult.training_label` maps draw → `"loss"` |
| 5 | No interest mechanic | — | Pack-1 does not have this; low priority |

---

## Enemy pool — fixed (Phase 1)

`AISimulator` in `src/game/ai_simulator.py` now fires all shop-phase events:

- `_fire_buy_events(shop, team)` — fires `buy` for the purchased pet and
  `friend_summoned` for every teammate with that trigger, then processes the
  queue. Called after every successful `shop.buy_pet()`.
- `_fire_end_of_turn(team)` — emits `end_of_turn` for the whole AI team before
  the battle snapshot (Giraffe, Monkey, Penguin, Bison now buff correctly).
- `_make_on_level_up(team)` — returns a closure passed as `on_level_up` to
  `Shop`, firing `level_up` + `friend_gains_xp` (Dragon) on combine.

**Validation:** `tests/test_smoke.py` runs 100 games and asserts mean team stats
at round 5 ≥ 20. Broken baseline (no events) measured at ~18.3; fixed at ~21.2.

---

## File map

```
main.py                      entry point (player game loop)
src/
  engine/
    ability_engine.py        all pet ability handlers + dispatch
    battle_engine.py         full battle resolution
    event_queue.py           priority queue with groundedsap.co.uk ordering
  shop/
    shop.py                  shop state, buy/sell/food/freeze/reroll
  game/
    game_state.py            player game state, round/gold/lives management
    ai_simulator.py          enemy pool generation  ← known gaps above
    data_loader.py           YAML → GameData
  models/
    pet.py / team.py         core data structures
    food.py / perk.py
  ui/
    console_ui.py            interactive terminal UI
Data/
  Pets.yaml                  all 30 Pack-1 pets (+ Sloth as secret: true)
  Foods.yaml                 all 12 foods
  Tokens.yaml                Cricket, Zombie Cricket, Bee, Fly token stats
```
