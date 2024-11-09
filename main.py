import yaml
import os

FOLDER_PATH = os.path.dirname(os.path.abspath(__file__))
FOODS_PATH = os.path.join(FOLDER_PATH, "Data", "Foods.yaml")
PETS_PATH = os.path.join(FOLDER_PATH, "Data", "Pets.yaml")

class Game:
    def __init__(self):
        self.pet_data = None
        self.food_data = None

    def load_data(self):
        """
        Function to load and save the data for all Foods and Pets in the Game object
        """
        
        # load Pet data
        with open(PETS_PATH, "r") as f:
            self.pet_data = yaml.safe_load(f)["Pets"]
        
        # load Food data
        with open(FOODS_PATH, "r") as f:
            self.food_data = yaml.safe_load(f)["Foods"]

class Team:
    def __init__(self, game_instance):
        self.game_instance = game_instance
        self.pets = None

    def create_team(self):
        pets = [Pet(self) for _ in range(5)]
        self.pets = pets

class Pet:
    def __init__(self, team):
        self.team = team
        self.name = "empty"
        self.attack =  0
        self.health = 0
        self.ability = {"trigger":"", "impact":"", "scaling":[0, 0, 0]}
        self.lvl = 0
        self.lvl_progress = 0
        self.perk = Perk()
    
    def assign_new_stats(self, stats):
        self.name = stats["name"]
        self.attack = stats["attack"]
        self.health = stats["health"]
        self.ability = stats["ability"]
        self.lvl = 1
        self.lvl_progress = 0
        self.perk = Perk()

class Food:
    def __init__(self):
        self.name = "empty"
        self.ability = None

class Perk:
    def __init__(self):
        self.name = "empty"
        self.ability = None

if __name__ == "__main__":

    Main = Game()
    Main.load_data()

    my_team = Team(Main)
    my_team.create_team()

    enemy_team = Team(Main)
    enemy_team.create_team()
