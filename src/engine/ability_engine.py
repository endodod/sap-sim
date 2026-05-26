from __future__ import annotations
import random
from typing import Callable, Optional
from src.models.pet import Pet
from src.models.team import Team
from src.engine.event_queue import Event, EventQueue

HandlerFn = Callable[["AbilityEngine", Event, Team, Team], list[Event]]


class AbilityEngine:
    def __init__(self, game_data=None):
        self.game_data = game_data
        self._handlers: dict[str, HandlerFn] = {}
        self._per_pet: dict[tuple[str, str], HandlerFn] = {}
        self._register_defaults()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_queue(self, queue: EventQueue, player: Team, enemy: Team, log: list[str]):
        while not queue.is_empty():
            event = queue.pop_next()
            new_events = self._dispatch(event, player, enemy, log)
            queue.push_all(new_events)

    def emit_for_all(self, trigger: str, team: Team, data: dict | None = None) -> list[Event]:
        events = []
        for pet in team.alive_pets:
            if pet.ability.get("trigger") == trigger:
                events.append(Event(trigger=trigger, source=pet, data=data or {}))
        return events

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    # Triggers that are allowed to fire even after the source pet has fainted
    _FAINT_TRIGGERS = frozenset({"faint", "after_faint"})

    def _dispatch(self, event: Event, player: Team, enemy: Team, log: list[str]) -> list[Event]:
        handler = self._handlers.get(event.trigger)
        if not handler or not event.source:
            return []
        # Faint abilities fire even though the source is dead
        if not event.source.is_alive and event.trigger not in self._FAINT_TRIGGERS:
            return []
        # Skip if source was removed from all teams (e.g. swallowed by a Whale)
        # while its event was already queued. Faint triggers are exempt because
        # the pet is still in slots until compact() runs after process_queue.
        if event.trigger not in self._FAINT_TRIGGERS:
            if (event.source not in player.all_pets
                    and event.source not in enemy.all_pets):
                return []
        return handler(self, event, player, enemy, log)

    def _register(self, trigger: str, fn: HandlerFn):
        self._handlers[trigger] = fn

    # ------------------------------------------------------------------
    # Ability handlers
    # ------------------------------------------------------------------

    def _register_defaults(self):

        # ── stat buff helpers ──────────────────────────────────────────

        def _give_random_friend_stats(eng, event, player, enemy, log):
            source = event.source
            team = _team_of(source, player, enemy)
            friends = [p for p in team.alive_pets if p is not source]
            if not friends:
                return []
            target = random.choice(friends)
            atk, hp = source.ability_scaling()
            target.buff(atk, hp)
            log.append(f"  {source.name} -> {target.name} +{atk}/+{hp}")
            return []

        def _give_two_friends_health(eng, event, player, enemy, log):
            source = event.source
            team = _team_of(source, player, enemy)
            friends = [p for p in team.alive_pets if p is not source]
            chosen = random.sample(friends, min(2, len(friends)))
            _, hp = source.ability_scaling()
            for t in chosen:
                t.buff(0, hp)
                log.append(f"  {source.name} -> {t.name} +0/+{hp}")
            return []

        def _give_all_friends_stats(eng, event, player, enemy, log):
            source = event.source
            team = _team_of(source, player, enemy)
            atk, hp = source.ability_scaling()
            for p in team.alive_pets:
                if p is not source:
                    p.buff(atk, hp)
            log.append(f"  {source.name} gave all friends +{atk}/+{hp}")
            return []

        def _give_friend_behind_stats(eng, event, player, enemy, log):
            source = event.source
            team = _team_of(source, player, enemy)
            target = team.pet_behind(source)
            if not target:
                return []
            atk, hp = source.ability_scaling()
            target.buff(atk, hp)
            log.append(f"  {source.name} -> {target.name} (behind) +{atk}/+{hp}")
            return []

        def _give_friend_ahead_stats(eng, event, player, enemy, log):
            source = event.source
            team = _team_of(source, player, enemy)
            target = team.pet_ahead(source)
            if not target:
                return []
            atk, hp = source.ability_scaling()
            target.buff(atk, hp)
            log.append(f"  {source.name} -> {target.name} (ahead) +{atk}/+{hp}")
            return []

        def _give_attack_to_friend_ahead(eng, event, player, enemy, log):
            # Dodo: give a fraction of own attack to friend ahead
            source = event.source
            team = _team_of(source, player, enemy)
            target = team.pet_ahead(source)
            if not target:
                return []
            atk, _ = source.ability_scaling()
            bonus = max(1, (source.effective_attack * atk) // 100) if atk > 10 else atk
            target.buff(bonus, 0)
            log.append(f"  {source.name} -> {target.name} (ahead) +{bonus} atk")
            return []

        def _give_two_friends_behind_stats(eng, event, player, enemy, log):
            # Flamingo
            source = event.source
            team = _team_of(source, player, enemy)
            idx = team.index_of(source)
            behind = [p for p in team.alive_pets if team.index_of(p) > idx][:2]
            atk, hp = source.ability_scaling()
            for t in behind:
                t.buff(atk, hp)
                log.append(f"  {source.name} -> {t.name} +{atk}/+{hp}")
            return []

        def _give_three_friends_ahead_stats(eng, event, player, enemy, log):
            # Giraffe
            source = event.source
            team = _team_of(source, player, enemy)
            idx = team.index_of(source)
            ahead = [p for p in team.alive_pets if team.index_of(p) < idx][-3:]
            atk, hp = source.ability_scaling()
            for t in ahead:
                t.buff(atk, hp)
            if ahead:
                log.append(f"  {source.name} gave {len(ahead)} friends ahead +{atk}/+{hp}")
            return []

        def _gain_stats(eng, event, player, enemy, log):
            source = event.source
            atk, hp = source.ability_scaling()
            source.buff(atk, hp)
            log.append(f"  {source.name} gained +{atk}/+{hp}")
            return []

        def _gain_attack(eng, event, player, enemy, log):
            source = event.source
            atk, _ = source.ability_scaling()
            source.buff(atk, 0)
            log.append(f"  {source.name} gained +{atk} atk")
            return []

        def _gain_random_stat(eng, event, player, enemy, log):
            # Dog: +1 atk or +1 hp randomly
            source = event.source
            if random.random() < 0.5:
                source.buff(1, 0)
                log.append(f"  {source.name} gained +1 atk")
            else:
                source.buff(0, 1)
                log.append(f"  {source.name} gained +1 hp")
            return []

        def _give_friend_temp_attack(eng, event, player, enemy, log):
            source = event.source
            summoned = event.data.get("summoned_pet")
            if summoned and summoned.is_alive:
                atk, _ = source.ability_scaling()
                summoned.temp_buff(atk, 0)
                log.append(f"  {source.name} -> {summoned.name} +{atk} temp atk")
            return []

        # ── damage helpers ─────────────────────────────────────────────

        def _deal_damage_random_enemy(eng, event, player, enemy, log):
            source = event.source
            team = _team_of(source, player, enemy)
            foe_team = enemy if team is player else player
            targets = foe_team.alive_pets
            if not targets:
                return []
            target = random.choice(targets)
            dmg, _ = source.ability_scaling()
            fainted = target.take_damage(dmg)
            log.append(f"  {source.name} snipes {target.name} for {dmg} dmg")
            new_events = []
            if fainted:
                new_events.append(Event("faint", source=target, data={"team": foe_team, "other_team": team}))
            else:
                new_events.append(Event("hurt", source=target, data={"team": foe_team, "other_team": team}))
            return new_events

        def _deal_damage_last_enemy(eng, event, player, enemy, log):
            # Crocodile
            source = event.source
            team = _team_of(source, player, enemy)
            foe_team = enemy if team is player else player
            alive = foe_team.alive_pets
            if not alive:
                return []
            target = alive[-1]
            dmg, _ = source.ability_scaling()
            fainted = target.take_damage(dmg)
            log.append(f"  {source.name} snipes last enemy {target.name} for {dmg} dmg")
            new_events = []
            if fainted:
                new_events.append(Event("faint", source=target, data={"team": foe_team, "other_team": team}))
            else:
                new_events.append(Event("hurt", source=target, data={"team": foe_team, "other_team": team}))
            return new_events

        def _deal_percent_damage_random_enemy(eng, event, player, enemy, log):
            # Leopard: deal % of own attack to random enemy
            source = event.source
            team = _team_of(source, player, enemy)
            foe_team = enemy if team is player else player
            targets = foe_team.alive_pets
            if not targets:
                return []
            target = random.choice(targets)
            pct, _ = source.ability_scaling()
            dmg = max(1, (source.effective_attack * pct) // 100)
            fainted = target.take_damage(dmg)
            log.append(f"  {source.name} snipes {target.name} for {dmg} dmg ({pct}%)")
            new_events = []
            if fainted:
                new_events.append(Event("faint", source=target, data={"team": foe_team, "other_team": team}))
            else:
                new_events.append(Event("hurt", source=target, data={"team": foe_team, "other_team": team}))
            return new_events

        def _deal_damage_all_pets(eng, event, player, enemy, log):
            # Hedgehog: 1 dmg to all pets
            source = event.source
            dmg, _ = source.ability_scaling()
            new_events = []
            for team in (player, enemy):
                for pet in list(team.alive_pets):
                    if pet is source:
                        continue
                    fainted = pet.take_damage(dmg)
                    if fainted:
                        other = enemy if team is player else player
                        new_events.append(Event("faint", source=pet, data={"team": team, "other_team": other}))
            log.append(f"  {source.name} dealt {dmg} dmg to all pets")
            return new_events

        def _deal_splash_damage_adjacent(eng, event, player, enemy, log):
            # Badger: deal half own attack to pets directly adjacent at time of faint
            source = event.source
            team = _team_of(source, player, enemy)
            foe_team = enemy if team is player else player
            dmg = max(1, source.effective_attack // 2)
            new_events = []
            for t_team, pet in [
                (team, team.pet_ahead(source)),
                (team, team.pet_behind(source)),
                (foe_team, foe_team.front),
            ]:
                if pet and pet.is_alive and pet is not source:
                    fainted = pet.take_damage(dmg)
                    if fainted:
                        other = foe_team if t_team is team else team
                        new_events.append(Event("faint", source=pet, data={"team": t_team, "other_team": other}))
                    break  # badger only hits front of enemy, not all
            log.append(f"  {source.name} splash dealt {dmg} dmg to adjacent")
            return new_events

        # ── summon helpers ─────────────────────────────────────────────

        def _summon_token(eng, event, player, enemy, log):
            source = event.source
            if eng.game_data is None:
                return []
            token_name = source.ability.get("token")
            if not token_name:
                return []
            team = _team_of(source, player, enemy)
            token = eng.game_data.make_token(token_name, level=source.level)
            placed = team.summon(token, after=source)
            if placed:
                log.append(f"  {source.name} summoned {token}")
                events = [Event("summoned", source=token, data={"team": team})]
                # Emit friend_summoned for each friendly pet that reacts to it
                for pet in team.alive_pets:
                    if pet is not token and pet.ability.get("trigger") == "friend_summoned":
                        events.append(Event("friend_summoned", source=pet,
                                            data={"team": team, "summoned_pet": token}))
                return events
            return []

        def _summon_two_tokens(eng, event, player, enemy, log):
            source = event.source
            if eng.game_data is None:
                return []
            token_name = source.ability.get("token", "ram")
            team = _team_of(source, player, enemy)
            new_events = []
            for _ in range(2):
                token = eng.game_data.make_token(token_name, level=source.level)
                placed = team.summon(token, after=source)
                if placed:
                    log.append(f"  {source.name} summoned {token}")
                    new_events.append(Event("summoned", source=token, data={"team": team}))
                    for pet in team.alive_pets:
                        if pet is not token and pet.ability.get("trigger") == "friend_summoned":
                            new_events.append(Event("friend_summoned", source=pet,
                                                    data={"team": team, "summoned_pet": token}))
            return new_events

        def _summon_enemy_token(eng, event, player, enemy, log):
            # Rat: summon dirty_rat on enemy front
            source = event.source
            if eng.game_data is None:
                return []
            token_name = source.ability.get("token", "dirty_rat")
            team = _team_of(source, player, enemy)
            foe_team = enemy if team is player else player
            token = eng.game_data.make_token(token_name, level=source.level)
            free = foe_team.first_empty_slot()
            if free is not None:
                foe_team.slots.insert(0, token)
                foe_team.slots = foe_team.slots[:5]
                while len(foe_team.slots) < 5:
                    foe_team.slots.append(None)
                log.append(f"  {source.name} summoned {token} on enemy team")
            return []

        def _summon_random_tier3_pet(eng, event, player, enemy, log):
            # Spider
            source = event.source
            if eng.game_data is None:
                return []
            team = _team_of(source, player, enemy)
            t3_names = eng.game_data.pets_by_tier(3)
            t3_names = [n for n in t3_names if eng.game_data.pets[n]["tier"] == 3]
            if not t3_names:
                return []
            name = random.choice(t3_names)
            pet = eng.game_data.make_pet(name)
            pet.level = 1
            placed = team.summon(pet, after=source)
            if placed:
                log.append(f"  {source.name} summoned tier-3 {pet.name}")
                evts = [Event("summoned", source=pet, data={"team": team})]
                for p2 in team.alive_pets:
                    if p2 is not pet and p2.ability.get("trigger") == "friend_summoned":
                        evts.append(Event("friend_summoned", source=p2, data={"team": team, "summoned_pet": pet}))
                return evts
            return []

        def _summon_random_tier6_pet(eng, event, player, enemy, log):
            # Eagle
            source = event.source
            if eng.game_data is None:
                return []
            team = _team_of(source, player, enemy)
            t6_names = [n for n in eng.game_data.pets if eng.game_data.pets[n]["tier"] == 6]
            if not t6_names:
                return []
            name = random.choice(t6_names)
            pet = eng.game_data.make_pet(name)
            placed = team.summon(pet, after=source)
            if placed:
                log.append(f"  {source.name} summoned tier-6 {pet.name}")
                evts = [Event("summoned", source=pet, data={"team": team})]
                for p2 in team.alive_pets:
                    if p2 is not pet and p2.ability.get("trigger") == "friend_summoned":
                        evts.append(Event("friend_summoned", source=p2, data={"team": team, "summoned_pet": pet}))
                return evts
            return []

        def _summon_zombie_fly_on_third(eng, event, player, enemy, log):
            # Fly: trigger on 3rd friend faint
            source = event.source
            source._faint_count = getattr(source, "_faint_count", 0) + 1
            if source._faint_count % 3 != 0:
                return []
            if eng.game_data is None:
                return []
            team = _team_of(source, player, enemy)
            fainted_pet = event.data.get("fainted")
            token = eng.game_data.make_token("zombie_fly", level=source.level)
            placed = team.summon(token, after=source) if fainted_pet is None else team.summon(token, after=source)
            if placed:
                log.append(f"  {source.name} summoned zombie fly")
                evts = [Event("summoned", source=token, data={"team": team})]
                for pet in team.alive_pets:
                    if pet is not token and pet.ability.get("trigger") == "friend_summoned":
                        evts.append(Event("friend_summoned", source=pet, data={"team": team, "summoned_pet": token}))
                return evts
            return []

        # ── special ability helpers ────────────────────────────────────

        def _copy_health_of_healthiest_friend(eng, event, player, enemy, log):
            # Crab
            source = event.source
            team = _team_of(source, player, enemy)
            friends = [p for p in team.alive_pets if p is not source]
            if not friends:
                return []
            healthiest = max(friends, key=lambda p: p.effective_health)
            new_hp = healthiest.effective_health
            old_hp = source.health
            source.health = new_hp
            log.append(f"  {source.name} copied {healthiest.name} health: {old_hp} -> {new_hp}")
            return []

        def _gain_perk(eng, event, player, enemy, log):
            # Scorpion on summon
            source = event.source
            from src.models.perk import Perk
            perk_name = source.ability.get("perk", "none")
            source.perk = Perk(name=perk_name, effect=perk_name)
            log.append(f"  {source.name} gained perk: {perk_name}")
            return []

        def _gain_perk_once_per_round(eng, event, player, enemy, log):
            # Gorilla: coconut shield once per round
            source = event.source
            if getattr(source, "_perk_used_this_round", False):
                return []
            from src.models.perk import Perk
            source.perk = Perk(name="coconut_shield", effect="coconut_shield")
            source._perk_used_this_round = True
            log.append(f"  {source.name} gained coconut_shield")
            return []

        def _give_pets_behind_perk(eng, event, player, enemy, log):
            # Turtle: give melon_armor to pets behind
            source = event.source
            team = _team_of(source, player, enemy)
            idx = team.index_of(source)
            behind = [p for p in team.alive_pets if team.index_of(p) > idx]
            from src.models.perk import Perk
            for t in behind:
                t.perk = Perk(name="melon_armor", effect="melon_armor")
                log.append(f"  {source.name} -> {t.name} melon_armor")
            return []

        def _give_friend_ahead_perk_and_attack(eng, event, player, enemy, log):
            # Ox: when friend ahead faints gain attack + bone_attack
            source = event.source
            atk, _ = source.ability_scaling()
            source.buff(atk, 0)
            from src.models.perk import Perk
            source.perk = Perk(name="bone_attack", effect="bone_attack")
            log.append(f"  {source.name} gained +{atk} atk + bone_attack perk")
            return []

        def _swallow_friend_ahead(eng, event, player, enemy, log):
            # Whale: swallow friend ahead at start of battle; re-summon at level of whale on faint
            source = event.source
            team = _team_of(source, player, enemy)
            target = team.pet_ahead(source)
            if not target:
                return []
            source._swallowed = target
            team.remove_pet(team.index_of(target))
            log.append(f"  {source.name} swallowed {target.name}")
            return []

        def _whale_faint_release(eng, event, player, enemy, log):
            # Whale releases swallowed pet on faint
            source = event.source
            swallowed = getattr(source, "_swallowed", None)
            if not swallowed:
                return []
            team = _team_of(source, player, enemy)
            placed = team.summon(swallowed, after=source)
            if placed:
                log.append(f"  {source.name} released {swallowed.name}")
                return [Event("summoned", source=swallowed, data={"team": team}),
                        Event("friend_summoned", source=swallowed, data={"team": team, "summoned_pet": swallowed})]
            return []

        def _gain_stats_if_all_max_level(eng, event, player, enemy, log):
            # Bison
            source = event.source
            team = _team_of(source, player, enemy)
            friends = [p for p in team.alive_pets if p is not source]
            if friends and all(p.level >= 3 for p in friends):
                atk, hp = source.ability_scaling()
                source.buff(atk, hp)
                log.append(f"  {source.name} gained +{atk}/+{hp} (all friends Lv3)")
            return []

        def _give_levelled_friends_stats(eng, event, player, enemy, log):
            # Penguin: give level 2+ friends +1/+1
            source = event.source
            team = _team_of(source, player, enemy)
            atk, hp = source.ability_scaling()
            targets = [p for p in team.alive_pets if p is not source and p.level >= 2]
            for t in targets:
                t.buff(atk, hp)
            if targets:
                log.append(f"  {source.name} gave Lv2+ friends +{atk}/+{hp}")
            return []

        def _give_friend_ahead_stats_end_turn(eng, event, player, enemy, log):
            # Monkey: give friend ahead +3/+3 at end of turn
            source = event.source
            team = _team_of(source, player, enemy)
            target = team.pet_ahead(source)
            if not target:
                return []
            atk, hp = source.ability_scaling()
            target.buff(atk, hp)
            log.append(f"  {source.name} -> {target.name} +{atk}/+{hp}")
            return []

        def _multiply_food_buff(eng, event, player, enemy, log):
            # Cat: multiply food buff — handled in shop food application
            return []

        def _add_milk_to_shop(eng, event, player, enemy, log):
            # Cow: handled in shop_phase via game_state
            return []

        def _gain_gold(eng, event, player, enemy, log):
            # Pig sell / Swan start_of_turn — handled via game_state gold tracking
            return []

        def _give_all_shop_pets_health(eng, event, player, enemy, log):
            # Duck sell — needs shop reference in event.data
            shop = event.data.get("shop")
            if shop is None:
                return []
            _, hp = event.source.ability_scaling()
            for slot in shop.pet_slots:
                if slot.item:
                    slot.item.buff(0, hp)
            log.append(f"  {event.source.name} gave shop pets +{hp} hp")
            return []

        def _give_friend_health_on_eat(eng, event, player, enemy, log):
            # Rabbit: when friend eats food
            source = event.source
            target = event.data.get("eating_pet")
            if not target or not target.is_alive:
                return []
            _, hp = source.ability_scaling()
            target.buff(0, hp)
            log.append(f"  {source.name} -> {target.name} +{hp} hp (ate food)")
            return []

        def _give_random_friend_attack(eng, event, player, enemy, log):
            # Shrimp: when friend is sold
            source = event.source
            team = _team_of(source, player, enemy)
            friends = [p for p in team.alive_pets if p is not source]
            if not friends:
                return []
            target = random.choice(friends)
            atk, _ = source.ability_scaling()
            target.buff(atk, 0)
            log.append(f"  {source.name} -> {target.name} +{atk} atk")
            return []

        # ── stubs for unimplemented or future handlers ─────────────────

        def _noop(eng, event, player, enemy, log):
            return []

        # ── per-pet routing map ────────────────────────────────────────

        self._per_pet = {
            # Tier 1
            ("friend_faints",   "ant"):         _give_random_friend_stats,
            ("sell",            "beaver"):      _give_two_friends_health,
            ("sell",            "duck"):        _give_all_shop_pets_health,
            ("sell",            "pig"):         _gain_gold,
            ("level_up",        "fish"):        _give_all_friends_stats,
            ("friend_summoned", "horse"):       _give_friend_temp_attack,
            ("start_of_battle", "mosquito"):    _deal_damage_random_enemy,
            ("faint",           "cricket"):     _summon_token,
            ("buy",             "otter"):       _give_random_friend_stats,
            # Tier 2
            ("start_of_battle", "crab"):        _copy_health_of_healthiest_friend,
            ("start_of_battle", "dodo"):        _give_attack_to_friend_ahead,
            ("faint",           "flamingo"):    _give_two_friends_behind_stats,
            ("faint",           "hedgehog"):    _deal_damage_all_pets,
            ("hurt",            "peacock"):     _gain_attack,
            ("faint",           "rat"):         _summon_enemy_token,
            ("friend_sold",     "shrimp"):      _give_random_friend_attack,
            ("faint",           "spider"):      _summon_random_tier3_pet,
            ("start_of_turn",   "swan"):        _gain_gold,
            ("faint",           "turtle"):      _give_pets_behind_perk,
            # Tier 3
            ("faint",           "badger"):      _deal_splash_damage_adjacent,
            ("hurt",            "blowfish"):    _deal_damage_random_enemy,
            ("hurt",            "camel"):       _give_friend_behind_stats,
            ("friend_summoned", "dog"):         _gain_random_stat,
            ("end_of_turn",     "giraffe"):     _give_three_friends_ahead_stats,
            ("friend_ahead_attacks", "kangaroo"): _gain_stats,
            ("friend_ahead_faints", "ox"):      _give_friend_ahead_perk_and_attack,
            ("friend_eats_food","rabbit"):      _give_friend_health_on_eat,
            ("faint",           "sheep"):       _summon_two_tokens,
            ("start_of_battle", "whale"):       _swallow_friend_ahead,
            # Tier 4
            ("end_of_turn",     "bison"):       _gain_stats_if_all_max_level,
            ("faint",           "deer"):        _summon_token,
            ("knock_out",       "hippo"):       _gain_stats,
            ("end_of_turn",     "monkey"):      _give_friend_ahead_stats_end_turn,
            ("end_of_turn",     "penguin"):     _give_levelled_friends_stats,
            # Tier 5
            ("buy",             "cow"):         _add_milk_to_shop,
            ("start_of_battle", "crocodile"):   _deal_damage_last_enemy,
            ("faint",           "eagle"):       _summon_random_tier6_pet,
            ("summoned",        "scorpion"):    _gain_perk,
            ("friend_faints",   "shark"):       _gain_stats,
            # Tier 6
            ("before_attack",   "boar"):        _gain_attack,
            ("friend_eats_food","cat"):         _multiply_food_buff,
            ("friend_gains_xp", "dragon"):      _give_all_friends_stats,
            ("friend_faints",   "fly"):         _summon_zombie_fly_on_third,
            ("hurt",            "gorilla"):     _gain_perk_once_per_round,
            ("start_of_battle", "leopard"):     _deal_percent_damage_random_enemy,
            # Whale faint special case
            ("faint",           "whale"):       _whale_faint_release,
        }

        def _routed_dispatch(eng, event, player, enemy, log):
            if event.source is None:
                return []
            key = (event.trigger, event.source.name)
            fn = eng._per_pet.get(key)
            if fn:
                return fn(eng, event, player, enemy, log)
            return []

        for trigger in {k[0] for k in self._per_pet}:
            self._register(trigger, _routed_dispatch)

        # Register stubs for triggers that have no per-pet handlers yet
        for trigger in ("before_battle", "after_attack", "after_faint",
                        "enemy_faints", "transformed", "none"):
            if trigger not in self._handlers:
                self._register(trigger, _noop)


# ── helpers ────────────────────────────────────────────────────────────────────

def _team_of(pet: Pet, player: Team, enemy: Team) -> Team:
    if pet in player.all_pets:
        return player
    return enemy
