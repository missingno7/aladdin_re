# Documentation

Three levels: the platform (shared Genesis machine, histories, replay,
verification — no game semantics), the recovery methodology (observe, bound,
recover, prove, continue, broaden — no game addresses), and the games (each
with its own status, knowledge, evidence and tooling).  Every document lives
under the level that owns its facts.

| I want to... | read |
|---|---|
| understand the repository's layout and what is shared versus per game | [common/architecture.md](common/architecture.md) |
| understand histories, checkpoints, caches and replay | [common/history-and-replay.md](common/history-and-replay.md) |
| understand how a region gets recovered and proven (the loop, the tools, the confidence hierarchy) | [common/recovery-process.md](common/recovery-process.md) |
| know what a claim is allowed to mean (recorded vs constructed, cached vs cold, oracle-assisted vs independent) | [common/evidence-model.md](common/evidence-model.md) |
| understand who owns the machine, the donor sources and the snapshot codec | [common/machine-ownership.md](common/machine-ownership.md) |
| understand how Aladdin converged on this process, and what it stopped doing | [aladdin/convergence.md](aladdin/convergence.md) |
| know what Aladdin runs today and what its evidence is | [aladdin/STATUS.md](aladdin/STATUS.md) |
| continue Aladdin's candidate grind | [aladdin/recovery-playbook.md](aladdin/recovery-playbook.md), [aladdin/grinder-goal.md](aladdin/grinder-goal.md), [aladdin/ledger.md](aladdin/ledger.md), [aladdin/blockers/](aladdin/blockers/) |
| continue Aladdin's native runtime | [aladdin/native-frontier.md](aladdin/native-frontier.md), [aladdin/semantic-map.md](aladdin/semantic-map.md), [aladdin/source-guide.md](aladdin/source-guide.md) |
| know what Gods runs today and what its evidence is | [gods/STATUS.md](gods/STATUS.md) |
| grind Gods | [gods/grinder-protocol.md](gods/grinder-protocol.md), [gods/grinder-goal.md](gods/grinder-goal.md), [gods/ledger.md](gods/ledger.md) |
| inspect old experiments, audits, specs and status logs | [archive/README.md](archive/README.md) |

## Ownership rules

- `common/` states facts about the shared layer and the methodology.  It
  names no game address, record layout, sound command or dispatcher.
- `aladdin/` and `gods/` state facts about one game.  A fact that changes
  often (what is recovered, what evidence passes, the next candidates) has
  one home, the game's `STATUS.md`; other documents link to it.
- `archive/` is history: what was believed at the time, kept for
  archaeology, not for operating instructions.  Archived documents carry a
  banner saying so; their commands and paths are those of their day.
- A worker grinding a game reads that game's `STATUS.md`, its grinder
  protocol and goal, its ledger, and `common/recovery-process.md`.  Nothing
  else is required reading.

## Adding a game

`common/architecture.md` §"What a third game adds".  Its documentation is a
`docs/<game>/STATUS.md` first, and a grinder protocol once the first region
has gone through the loop.
