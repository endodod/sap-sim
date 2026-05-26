import sys
from src.game.data_loader import DataLoader
from src.game.game_state import GameState
from src.game.ai_simulator import AISimulator
from src.game.enemy_pool import EnemyPool
from src.ui.console_ui import ConsoleUI

POOL_PATH = "enemy_pool.pkl"
AI_GAMES = 10


def main():
    print("Loading game data...")
    data = DataLoader().load()

    if EnemyPool.exists(POOL_PATH):
        print("Loading enemy pool...")
        pool = EnemyPool.load(POOL_PATH)
    else:
        print(f"Simulating {AI_GAMES} AI games to build enemy pool...")
        sim = AISimulator(data)
        raw_pool = sim.run_games(AI_GAMES)
        pool = EnemyPool(raw_pool)
        pool.save(POOL_PATH)
        print(f"Enemy pool ready: {pool.size()} teams across rounds {pool.rounds_covered()}")

    state = GameState(data, enemy_pool=pool)
    ui = ConsoleUI(state)
    ui.run()


if __name__ == "__main__":
    main()
