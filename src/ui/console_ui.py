from __future__ import annotations
import os
from src.game.game_state import GameState
from src.shop.shop import Shop
from src.models.team import Team

_ABILITY_LABELS = {
    "friend_faints":        "Friend faints",
    "sell":                 "On sell",
    "buy":                  "On buy",
    "level_up":             "On level up",
    "start_of_battle":      "Start of battle",
    "start_of_turn":        "Start of turn",
    "end_of_turn":          "End of turn",
    "faint":                "On faint",
    "hurt":                 "On hurt",
    "knock_out":            "Knock out",
    "friend_summoned":      "Friend summoned",
    "friend_ahead_attacks": "Friend ahead attacks",
    "friend_ahead_faints":  "Friend ahead faints",
    "friend_sold":          "Friend sold",
    "friend_eats_food":     "Friend eats food",
    "friend_gains_xp":      "Friend gains XP",
    "before_attack":        "Before attack",
    "summoned":             "On summon",
    "none":                 "",
}

_EFFECT_LABELS = {
    "give_random_friend_stats":         "Give random friend +ATK/+HP",
    "give_two_friends_health":          "Give 2 friends +HP",
    "give_all_friends_stats":           "Give all friends +ATK/+HP",
    "give_friend_behind_stats":         "Give friend behind +ATK/+HP",
    "give_friend_ahead_stats":          "Give friend ahead +ATK/+HP",
    "give_attack_to_friend_ahead":      "Give ATK to friend ahead",
    "give_two_friends_behind_stats":    "Give 2 friends behind +ATK/+HP",
    "give_three_friends_ahead_stats":   "Give 3 friends ahead +ATK/+HP",
    "give_all_shop_pets_health":        "Give all shop pets +HP",
    "give_levelled_friends_stats":      "Give Lv2+ friends +ATK/+HP",
    "give_friend_ahead_stats_end_turn": "Give friend ahead +ATK/+HP",
    "give_pets_behind_perk":            "Give pets behind melon armor",
    "give_friend_health":               "Give friend +HP",
    "give_friend_health_on_eat":        "Give friend who ate +HP",
    "give_random_friend_attack":        "Give random friend +ATK",
    "give_stats_if_all_friends_max_level": "If all friends Lv3, gain +ATK/+HP",
    "gain_attack_and_perk":             "Gain +ATK + bone attack",
    "gain_stats":                       "Gain +ATK/+HP",
    "gain_attack":                      "Gain +ATK",
    "gain_random_stat":                 "Gain +ATK or +HP randomly",
    "gain_perk":                        "Gain perk on summon",
    "gain_perk_once_per_round":         "Gain coconut shield (1x/round)",
    "gain_gold":                        "Gain gold",
    "deal_damage_random_enemy":         "Deal DMG to random enemy",
    "deal_damage_last_enemy":           "Deal DMG to last enemy",
    "deal_percent_damage_random_enemy": "Deal % ATK to random enemy",
    "deal_damage_all_pets":             "Deal 1 DMG to all pets",
    "deal_splash_damage_adjacent":      "Deal half ATK to adjacent",
    "summon_token":                     "Summon token",
    "summon_two_tokens":                "Summon 2 tokens",
    "summon_enemy_token":               "Summon token on enemy",
    "summon_random_tier3_pet":          "Summon random tier-3 pet",
    "summon_random_tier6_pet":          "Summon random tier-6 pet",
    "summon_zombie_fly_on_third":       "Summon Zombie Fly (every 3rd faint)",
    "copy_health_of_healthiest_friend": "Copy healthiest friend's HP",
    "swallow_friend_ahead":             "Swallow friend ahead; release on faint",
    "multiply_food_buff":               "Multiply food buffs",
    "add_milk_to_shop":                 "Add free Milk to shop",
    "give_all_future_shop_pets_stats":  "All future shop pets +ATK/+HP",
    "give_target_stats":                "Give chosen pet +ATK/+HP",
    "give_target_temp_stats":           "Give chosen pet temp +ATK/+HP",
    "give_two_random_friends_stats":    "Give 2 random friends +ATK/+HP",
    "give_three_random_friends_stats":  "Give 3 random friends +ATK/+HP",
    "give_perk":                        "Give chosen pet a perk",
    "give_target_random_perk":          "Give chosen pet random perk",
    "faint_target":                     "Faint chosen pet (triggers ability)",
    "none":                             "No ability",
}


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def describe_ability(ability: dict) -> str:
    if not ability:
        return ""
    trigger = ability.get("trigger", "none")
    effect = ability.get("effect", "none")
    if trigger == "none" or effect == "none":
        return ""
    t_label = _ABILITY_LABELS.get(trigger, trigger)
    e_label = _EFFECT_LABELS.get(effect, effect)
    scaling = ability.get("scaling", [[0, 0]])
    if scaling and scaling[0] != [0, 0]:
        s = scaling[0]
        if s[1] == 0:
            e_label += f" ({s[0]})"
        elif s[0] == 0:
            e_label += f" (+{s[1]} hp)"
        else:
            e_label += f" (+{s[0]}/+{s[1]})"
    return f"[{t_label}] {e_label}"


class ConsoleUI:
    def __init__(self, state: GameState):
        self.state = state

    # ------------------------------------------------------------------
    # Main game loop
    # ------------------------------------------------------------------

    def run(self):
        self.state.start_turn()
        while not self.state.is_over():
            self._shop_phase()
            if self.state.is_over():
                break
            result_data = self.state.end_turn()
            self._battle_phase(result_data)
            if result_data["game_over"] or result_data["victory"]:
                break
            self.state.start_turn()
        self._end_screen()

    # ------------------------------------------------------------------
    # Shop phase
    # ------------------------------------------------------------------

    def _shop_phase(self):
        msg = ""
        while True:
            _clear()
            self._render_header()
            self._render_team(self.state.player_team)
            self._render_shop(self.state.shop)
            self._render_help()
            if msg:
                print(f"\n  -> {msg}")
                msg = ""

            raw = input("\n> ").strip().lower()
            if not raw:
                continue
            parts = raw.split()
            cmd = parts[0]

            if cmd == "end":
                break

            elif cmd == "buy" and len(parts) >= 2:
                try:
                    shop_idx = int(parts[1]) - 1
                    team_slot = int(parts[2]) - 1 if len(parts) >= 3 else None
                    ok, m = self.state.buy_pet(shop_idx, team_slot)
                    msg = m
                except (ValueError, IndexError):
                    msg = "Usage: buy <shop#> [team_slot#]"

            elif cmd == "food" and len(parts) >= 2:
                try:
                    food_idx = int(parts[1]) - 1
                    target = int(parts[2]) - 1 if len(parts) >= 3 else None
                    ok, m = self.state.buy_food(food_idx, target)
                    msg = m
                except (ValueError, IndexError):
                    msg = "Usage: food <f#> [team_slot#]"

            elif cmd == "sell" and len(parts) >= 2:
                try:
                    slot = int(parts[1]) - 1
                    ok, m = self.state.sell_pet(slot)
                    msg = m
                except (ValueError, IndexError):
                    msg = "Usage: sell <team_slot#>"

            elif cmd == "move" and len(parts) >= 3:
                try:
                    f = int(parts[1]) - 1
                    t = int(parts[2]) - 1
                    ok, m = self.state.move_pet(f, t)
                    msg = m
                except (ValueError, IndexError):
                    msg = "Usage: move <from#> <to#>"

            elif cmd == "reroll":
                ok, m = self.state.reroll()
                msg = m

            elif cmd in ("freeze", "fz") and len(parts) >= 2:
                try:
                    idx = int(parts[1]) - 1
                    is_food = len(parts) >= 3 and parts[2] == "food"
                    ok, m = self.state.freeze(idx, is_food)
                    msg = m
                except (ValueError, IndexError):
                    msg = "Usage: freeze <#> [food]"

            elif cmd == "help":
                self._show_help()

            else:
                msg = "Unknown command. Type 'help' for reference."

    # ------------------------------------------------------------------
    # Battle phase
    # ------------------------------------------------------------------

    def _battle_phase(self, result_data: dict):
        result = result_data["result"]
        turns = self._split_log_by_turn(result.log)

        _clear()
        self._render_header()
        print("\n=== BATTLE ===")
        for turn_lines in turns:
            for line in turn_lines:
                print(line)
            if len(turns) > 1:
                input("  [Enter for next turn]")

        print()
        if result_data["game_over"]:
            print("  You have no lives left. GAME OVER.")
        elif result_data["victory"]:
            print(f"  You reached {self.state.wins} wins. VICTORY!")
        else:
            w = result.winner.upper()
            streak = ""
            if self.state.win_streak >= 2:
                streak = f"  Win streak: {self.state.win_streak}!"
            elif self.state.loss_streak >= 2:
                streak = f"  Loss streak: {self.state.loss_streak}."
            print(f"  Result: {w}  |  Lives: {result_data['lives']}  |  Wins: {result_data['wins']}{streak}")
        input("\n  [Enter to continue]")

    def _split_log_by_turn(self, log: list[str]) -> list[list[str]]:
        turns = []
        current = []
        for line in log:
            if line.startswith("\n") and current:
                turns.append(current)
                current = [line]
            else:
                current.append(line)
        if current:
            turns.append(current)
        return turns if turns else [log]

    # ------------------------------------------------------------------
    # End screen
    # ------------------------------------------------------------------

    def _end_screen(self):
        _clear()
        if self.state.wins >= 10:
            print("======================")
            print("      VICTORY!        ")
            print(f"  Wins:   {self.state.wins}/10")
            print(f"  Rounds: {self.state.round}")
            print("======================")
        else:
            print("======================")
            print("      GAME OVER       ")
            print(f"  Lives: 0/10")
            print(f"  Wins:  {self.state.wins}/10")
            print(f"  Round: {self.state.round}")
            print("======================")

    # ------------------------------------------------------------------
    # Renderers
    # ------------------------------------------------------------------

    def _render_header(self):
        s = self.state
        streak_info = ""
        if s.win_streak >= 2:
            streak_info = f"  [W-streak: {s.win_streak} +{s._streak_bonus()}g]"
        elif s.loss_streak >= 2:
            streak_info = f"  [L-streak: {s.loss_streak} +{s._streak_bonus()}g]"
        print(f"  Round {s.round}   Gold: {s.gold}g   Lives: {s.lives}/10   Wins: {s.wins}/10{streak_info}")
        print("-" * 65)

    def _render_team(self, team: Team):
        print("\n  YOUR TEAM")
        for i, pet in enumerate(team.slots):
            if pet:
                xp_max = pet.XP_TO_LEVEL.get(pet.level, "-")
                xp_str = f"({pet.xp}/{xp_max}xp)" if pet.level < 3 else "(maxlv)"
                temp_str = ""
                if pet.temp_attack or pet.temp_health:
                    temp_str = f" [+{pet.temp_attack}t/+{pet.temp_health}t]"
                perk_str = f" <{pet.perk.name}>" if pet.perk.name != "none" else ""
                ability_str = describe_ability(pet.ability)
                print(f"  [{i+1}] {pet.name:<12} Lv{pet.level}{xp_str}  {pet.effective_attack:>2}/{pet.effective_health:<3}{temp_str}{perk_str}")
                if ability_str:
                    print(f"       {ability_str}")
            else:
                print(f"  [{i+1}] --- empty ---")
        print()

    def _render_shop(self, shop: Shop):
        tier_label = f"Tier {shop.tier}"
        print(f"  SHOP  ({tier_label}, reroll 1g)")
        for i, slot in enumerate(shop.pet_slots):
            fz = " [FZ]" if slot.frozen else "      "
            if slot.item:
                p = slot.item
                ability_str = describe_ability(p.ability)
                print(f"  [{i+1}]{fz} {p.name:<12} {p.effective_attack}/{p.effective_health}  (3g)")
                if ability_str:
                    print(f"         {ability_str}")
            else:
                print(f"  [{i+1}]{fz} --- sold ---")
        if shop.food_slots:
            print()
        for i, slot in enumerate(shop.food_slots):
            fz = " [FZ]" if slot.frozen else "      "
            if slot.item:
                f = slot.item
                ability_str = describe_ability(f.ability)
                needs_target = f.ability.get("target") in ("chosen_friend",)
                target_hint = "  (specify slot)" if needs_target else ""
                print(f"  [f{i+1}]{fz} {f.name:<14} ({f.cost}g){target_hint}")
                if ability_str:
                    print(f"         {ability_str}")
            else:
                print(f"  [f{i+1}]{fz} --- sold ---")

    def _render_help(self):
        print("\n  buy <#> [slot]  |  sell <slot>  |  food <f#> [slot]  |  move <a> <b>")
        print("  reroll  |  freeze <#> [food]  |  end  |  help")

    def _show_help(self):
        _clear()
        print("=== HELP ===\n")
        print("  buy <shop#> [team_slot]  - Buy pet from shop. Optionally specify which team slot.")
        print("  sell <team_slot>         - Sell pet for 1g (+ ability bonus).")
        print("  food <f#> [team_slot]    - Buy food. Some foods need a target slot.")
        print("  move <from> <to>         - Swap or move pets on your team.")
        print("  reroll                   - Reroll shop (1g).")
        print("  freeze <#> [food]        - Freeze/unfreeze a shop slot. Add 'food' for food slots.")
        print("  end                      - End shop phase and battle.")
        print("  help                     - Show this screen.\n")
        print("  Slots are 1-indexed. Team slots: 1-5. Shop pet slots: 1-5. Food slots: f1-f2.\n")
        print("  TIPS:")
        print("  - Front of team = slot 1. Pets fight front-to-front.")
        print("  - Buying 3 of the same pet merges them (level up).")
        print("  - Temp buffs (+t) expire after battle.")
        print("  - Perks (<name>) activate automatically in battle.")
        print()
        input("  [Enter to return]")
