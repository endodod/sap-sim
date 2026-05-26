# SuperAutoPetsSimulation

Python simulation of Super Auto Pets — playable via terminal and designed as a base for AI training.

## Run

```bash
python main.py
```

## Structure

```
src/engine/     battle resolution, ability dispatch, event queue
src/shop/       shop state (buy, sell, food, freeze, reroll)
src/game/       game loop, AI enemy-pool generator, data loader
src/models/     Pet, Team, Food, Perk
src/ui/         terminal UI
Data/           Pets.yaml, Foods.yaml, Tokens.yaml
```

## Coverage

- All 30 Pack-1 pets with working ability handlers
- Full battle phase order matching [groundedsap.co.uk](https://www.groundedsap.co.uk/)
- Shop mechanics: tiers, combine/level-up, freeze, all 12 foods, sell-triggers
- Sloth easter egg: 1/10 000 chance per fill in the leftmost unfrozen slot

## For AI training

Read **HANDSHAKE.md** before building a training loop. It documents what is complete, what is stubbed out, and the known enemy-pool quality problem (AI teams are generated without shop-phase ability procs, making them weaker than realistic opponents).

## Reference

Game data and mechanics from [Grounded SAP](https://www.groundedsap.co.uk/).
