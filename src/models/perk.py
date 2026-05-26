class Perk:
    def __init__(self, name: str = "none", effect: str = "none"):
        self.name = name
        self.effect = effect
        self.used = False  # consumed perks (bone_attack, melon_armor, coconut_shield)

    def reset(self):
        self.used = False

    def __repr__(self):
        return f"Perk({self.name})"
