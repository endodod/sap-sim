class Food:
    def __init__(self, name: str, tier: int, cost: int, ability: dict):
        self.name = name
        self.tier = tier
        self.cost = cost
        self.ability = ability

    def __repr__(self):
        return f"Food({self.name})"
