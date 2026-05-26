import os
import yaml
from src.models.pet import Pet
from src.models.food import Food


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "Data")


class GameData:
    def __init__(self, pets: dict, foods: dict, tokens: dict):
        self.pets = pets        # name -> Pet template dict
        self.foods = foods      # name -> Food template dict
        self.tokens = tokens    # name -> Pet template dict (tokens)

    def make_pet(self, name: str) -> Pet:
        d = self.pets[name]
        return Pet(
            name=name,
            attack=d["attack"],
            health=d["health"],
            tier=d["tier"],
            ability=d["ability"],
        )

    def make_token(self, name: str, level: int = 1) -> Pet:
        d = self.tokens[name]
        scaling = d["ability"]["scaling"]
        idx = min(level - 1, len(scaling) - 1)
        atk, hp = scaling[idx]
        pet = Pet(
            name=name,
            attack=atk,
            health=hp,
            tier=0,
            ability=d["ability"],
            is_token=True,
        )
        return pet

    def make_food(self, name: str) -> Food:
        d = self.foods[name]
        return Food(
            name=name,
            tier=d["tier"],
            cost=d["cost"],
            ability=d["ability"],
        )

    def pets_by_tier(self, max_tier: int) -> list[str]:
        return [n for n, d in self.pets.items()
                if d["tier"] <= max_tier and not d.get("secret")]

    def foods_by_tier(self, max_tier: int) -> list[str]:
        return [n for n, d in self.foods.items() if d["tier"] <= max_tier]


class DataLoader:
    def load(self) -> GameData:
        pets = self._load_yaml("Pets.yaml")
        foods = self._load_yaml("Foods.yaml")
        tokens = self._load_yaml("Tokens.yaml")
        return GameData(pets=pets, foods=foods, tokens=tokens)

    def _load_yaml(self, filename: str) -> dict:
        path = os.path.join(DATA_DIR, filename)
        with open(path, "r") as f:
            return yaml.safe_load(f)
