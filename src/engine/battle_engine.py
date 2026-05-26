from __future__ import annotations
import copy
from dataclasses import dataclass
from typing import Optional
from src.models.team import Team
from src.models.pet import Pet
from src.engine.event_queue import Event, EventQueue
from src.engine.ability_engine import AbilityEngine, _team_of

BONE_ATTACK_BONUS = 5


@dataclass
class BattleResult:
    winner: str          # "player", "enemy", or "draw"
    player_survivors: int
    enemy_survivors: int
    log: list[str]


class BattleEngine:
    MAX_TURNS = 50

    def __init__(self, ability_engine: AbilityEngine):
        self.ae = ability_engine

    def run(self, player: Team, enemy: Team) -> BattleResult:
        p = copy.deepcopy(player)
        e = copy.deepcopy(enemy)
        log: list[str] = []

        self._phase_start_of_battle(p, e, log)

        turns = 0
        while not p.is_empty() and not e.is_empty() and turns < self.MAX_TURNS:
            turns += 1
            self._do_attack_turn(p, e, log)

        p_alive = len(p.alive_pets)
        e_alive = len(e.alive_pets)
        if p_alive > e_alive:
            winner = "player"
        elif e_alive > p_alive:
            winner = "enemy"
        else:
            winner = "draw"

        log.append(f"\n=== Battle over: {winner.upper()} wins ===")
        return BattleResult(winner=winner, player_survivors=p_alive, enemy_survivors=e_alive, log=log)

    def _phase_start_of_battle(self, p: Team, e: Team, log: list[str]):
        log.append("--- Start of Battle ---")
        queue = EventQueue()
        for team in (p, e):
            queue.push_all(self.ae.emit_for_all("start_of_battle", team))
        self.ae.process_queue(queue, p, e, log)
        self._remove_dead(p, e, log, queue)

    def _do_attack_turn(self, p: Team, e: Team, log: list[str]):
        p_front = p.front
        e_front = e.front
        if not p_front or not e_front:
            return

        log.append(f"\n{p_front} vs {e_front}")
        queue = EventQueue()

        # Before attack (e.g. boar gains +2 atk)
        queue.push_all(self.ae.emit_for_all("before_attack", p))
        queue.push_all(self.ae.emit_for_all("before_attack", e))
        self.ae.process_queue(queue, p, e, log)

        # Calculate damage with perk bonuses
        p_dmg = _attack_damage(p_front)
        e_dmg = _attack_damage(e_front)

        # Melon armor absorbs first hit
        p_fainted = _apply_damage(e_front, p_dmg, log)
        e_fainted = _apply_damage(p_front, e_dmg, log)

        log.append(f"  {p_front.name} deals {p_dmg} dmg -> {e_front.name} ({e_front.health} hp left)")
        log.append(f"  {e_front.name} deals {e_dmg} dmg -> {p_front.name} ({p_front.health} hp left)")

        # Hurt / faint / knock out events
        if not e_fainted:
            queue.push(Event("hurt", source=e_front, data={"team": e, "other_team": p}))
        if not p_fainted:
            queue.push(Event("hurt", source=p_front, data={"team": p, "other_team": e}))

        if p_fainted:
            queue.push(Event("faint", source=e_front, data={"team": e, "other_team": p}))
            queue.push(Event("knock_out", source=e_front, data={"team": e}))
            queue.push_all(self._friend_faint_events(e_front, p, "friend_faints"))
        if e_fainted:
            queue.push(Event("faint", source=p_front, data={"team": p, "other_team": e}))
            queue.push(Event("knock_out", source=p_front, data={"team": p}))
            queue.push_all(self._friend_faint_events(p_front, e, "friend_faints"))

        self.ae.process_queue(queue, p, e, log)
        self._remove_dead(p, e, log, queue)

        # After attack + friend_ahead_attacks
        queue.push_all(self.ae.emit_for_all("after_attack", p))
        queue.push_all(self.ae.emit_for_all("after_attack", e))
        # Kangaroo: friend ahead just attacked
        for team in (p, e):
            front = team.front
            if front:
                for pet in team.alive_pets:
                    if pet is not front and pet.ability.get("trigger") == "friend_ahead_attacks":
                        if team.pet_ahead(pet) is front:
                            queue.push(Event("friend_ahead_attacks", source=pet, data={"team": team}))
        self.ae.process_queue(queue, p, e, log)

        p.compact()
        e.compact()

    def _friend_faint_events(self, fainted: Pet, other_team: Team, trigger: str) -> list[Event]:
        events = []
        for pet in other_team.alive_pets:
            if pet.ability.get("trigger") == trigger:
                events.append(Event(trigger, source=pet, data={"fainted": fainted}))
        return events

    def _remove_dead(self, p: Team, e: Team, log: list[str], queue: EventQueue):
        for team, name in ((p, "player"), (e, "enemy")):
            for pet in team.all_pets:
                if not pet.is_alive:
                    log.append(f"  {pet.name} fainted ({name})")
            team.compact()


# ── perk helpers ──────────────────────────────────────────────────────────────

def _attack_damage(attacker: Pet) -> int:
    dmg = attacker.effective_attack
    if attacker.perk.name == "bone_attack" and not attacker.perk.used:
        dmg += BONE_ATTACK_BONUS
        attacker.perk.used = True
    return dmg


def _apply_damage(target: Pet, dmg: int, log: list[str]) -> bool:
    """Apply damage respecting melon_armor / coconut_shield. Returns True if fainted."""
    perk = target.perk
    if perk.name == "melon_armor" and not perk.used:
        perk.used = True
        log.append(f"  {target.name} melon armor absorbed hit")
        return False
    if perk.name == "coconut_shield" and not perk.used:
        perk.used = True
        log.append(f"  {target.name} coconut shield absorbed hit")
        return False
    if perk.name == "poisoned_attack":
        # Scorpion: target gets poisoned (one-shot kill regardless of health)
        target.health = 0
        target.is_alive = False
        log.append(f"  {target.name} poisoned -> instant faint")
        return True
    return target.take_damage(dmg)
