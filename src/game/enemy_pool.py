from __future__ import annotations
import copy
import pickle
import random
import os
from src.models.team import Team


class EnemyPool:
    """
    Stores team snapshots keyed by round number.
    Used to supply realistic enemy teams during gameplay.
    """

    def __init__(self, pool: dict[int, list[Team]] | None = None):
        self._pool: dict[int, list[Team]] = pool or {}

    def add(self, round_num: int, team: Team):
        self._pool.setdefault(round_num, []).append(copy.deepcopy(team))

    def get_enemy(self, round_num: int) -> Team:
        """Return a random team from the pool for this round, falling back to nearest round."""
        if round_num in self._pool and self._pool[round_num]:
            return copy.deepcopy(random.choice(self._pool[round_num]))
        # Fall back: find nearest round with data
        available = sorted(self._pool.keys())
        if not available:
            return Team()
        # Pick closest round <= round_num, then closest above
        below = [r for r in available if r <= round_num]
        if below:
            return copy.deepcopy(random.choice(self._pool[max(below)]))
        return copy.deepcopy(random.choice(self._pool[available[0]]))

    def size(self) -> int:
        return sum(len(v) for v in self._pool.values())

    def rounds_covered(self) -> list[int]:
        return sorted(self._pool.keys())

    def save(self, path: str):
        with open(path, "wb") as f:
            pickle.dump(self._pool, f)

    @classmethod
    def load(cls, path: str) -> "EnemyPool":
        with open(path, "rb") as f:
            pool = pickle.load(f)
        return cls(pool)

    @classmethod
    def exists(cls, path: str) -> bool:
        return os.path.exists(path)
