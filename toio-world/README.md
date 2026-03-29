# toio-world

Small, stable playground for `toio` world-model experiments.

This package is intentionally biased toward:

- repeatable data collection
- append-only episode logs
- replayable action sequences
- simple baselines before heavy learning

The first goal is not to publish a paper. It is to create a causally dense mini-world
that is fun to play with and stable enough to train on later.

## Scope

`toio-world` sits next to `toio-mcp`.

- `toio-mcp` is the MCP-facing hand for interactive control
- `toio-world` is the robotics and learning sandbox

This split keeps the experiment loop simple:

1. move the cube
2. log what happened
3. replay it
4. fit a tiny model

## Layout

```text
toio-world/
  configs/
    world.toml
    policies.toml
  assets/
    markers/
    mats/
  episodes/
  scripts/
    collect_random.py
    collect_pattern.py
    collect_calibration.py
    discover_concepts.py
    discover_macros.py
    derive_symbols.py
    compile_vocabulary.py
    profile_actions.py
    replay_episode.py
    review_protolang.py
    inspect_episode.py
    mine_rules.py
    train_next_pose.py
    eval_next_pose.py
  src/toio_world/
    align.py
    baseline.py
    cli.py
    config.py
    concepts.py
    controller.py
    dataset.py
    discover.py
    induce.py
    logger.py
    policies.py
    protolang.py
    replay.py
    review.py
    schema.py
    vocabulary.py
    visualize.py
  tests/
```

## Quick Start

Install dependencies:

```bash
cd toio-world
uv sync --extra dev
```

Collect a mock episode without hardware:

```bash
uv run toio-world collect-pattern square --episode-root episodes --backend mock
```

Collect a repeated discrete-action calibration sweep:

```bash
uv run python scripts/collect_calibration.py --backend mock --repeats 8
```

Inspect the resulting run:

```bash
uv run toio-world inspect episodes/<episode-id>
```

Replay the same episode against the mock controller:

```bash
uv run toio-world replay episodes/<episode-id> --backend mock
```

Fit the first baseline:

```bash
uv run python scripts/train_next_pose.py episodes/<episode-id>
```

The first baseline is deliberately simple: mean pose delta per action type.
It is a sanity check, not a final model.

Evaluate that baseline on one or more episodes:

```bash
uv run python scripts/eval_next_pose.py \
  episodes/<episode-id>/baseline-next-pose.json \
  episodes/<episode-id>
```

Fit an action profile from calibration episodes:

```bash
uv run python scripts/profile_actions.py episodes/<episode-id>
```

This writes `action-profile.json` with mean/std deltas per action. It is the first honest
bridge between nominal action names and the real cube's behavior.

Derive the first proto-language layer:

```bash
uv run python scripts/derive_symbols.py episodes/<episode-id>
```

This writes:

- `symbols.jsonl`: symbolized transitions
- `gloss-table.json`: empty human-language alignment table

Discover repeated action chunks:

```bash
uv run python scripts/discover_macros.py episodes/<episode-id>
```

Discover compressed state concepts:

```bash
uv run python scripts/discover_concepts.py episodes/<episode-id>
```

Mine simple transition rules:

```bash
uv run python scripts/mine_rules.py episodes/<episode-id>
```

Review the top internal concepts in one place:

```bash
uv run python scripts/review_protolang.py episodes/<episode-id>
```

Compile a single working vocabulary surface for curation:

```bash
uv run python scripts/compile_vocabulary.py episodes/<episode-id>
```

Both outputs are ranked so that more interesting internal concepts float upward first.
By default:

- macros are discovered with state conditioning enabled
- low-value rules such as `TRANSITION_VALID` and `ROT_NONE` are dropped
- rules may use up to two state symbols plus the action as their antecedent
- the working vocabulary keeps one shared surface for `symbol`, `concept`, `macro`, and `rule`
- glosses remain hints layered over internal names rather than replacing them

## Real Hardware

The current scaffold ships with:

- `MockController`: works now, used in tests and dry runs
- `ToioController`: placeholder interface for `toio.py` integration

Once the cube arrives, wire `ToioController` to the official Python stack:

- `toio.py`: <https://github.com/toio/toio.py>
- toio technical spec: <https://toio.github.io/toio-spec/>
- hardware dependency: `uv sync --extra dev`

`ToioController` now targets `toio.py`'s `SimpleCube` surface directly.
By default it reads:

- `TOIO_CUBE_NAME`: optional cube name filter
- `TOIO_SCAN_TIMEOUT`: scan timeout in seconds
- `TOIO_SPEED`: default movement speed for discrete actions

Discrete actions use `move_steps()` and `turn()` so the first real datasets can stay
close to the position-id world. Raw `move` actions still go through `run_motor()`.

The first recommended real-hardware loop is:

1. `collect_calibration.py`
2. `profile_actions.py`
3. `collect-pattern square --backend toio`
4. compare nominal actions against the calibration profile before trusting learned rules

The rest of the package should stay unchanged.

## Design Rules

1. Keep the episode schema stable.
2. Store both raw commands and derived deltas.
3. Prefer replayability over clever abstractions.
4. Start with position truth before adding external camera vision.
5. Add learning only after logging and replay feel boringly reliable.

## Data Strategy

For this project, "a lot of data" should mean:

- many transitions
- many repeated interventions
- many recoverable failures
- many short sequences with clear cause and effect

It should not mean collecting endless unstructured still images.

The first useful dataset is sensorimotor:

```text
pre-state -> action -> post-state
```

Once that is stable, add external observations:

- top-down camera frames
- room sensor snapshots
- human labels

Then derive a primitive symbolic layer:

- coarse state symbols such as `HEADING_E`, `X_LOW`, `NEAR_EDGE_X_MAX`
- action symbols such as `ACT_FORWARD_SHORT`
- change symbols such as `MOVE_FAIL`, `ROT_LEFT`

Only after that should you start attaching human-language glosses.

After primitive symbols, grow the proto-language in two directions:

- `macro-candidates.json`: repeated action chunks such as `ACT_FORWARD_LONG + ACT_TURN_LEFT_LARGE`
- `rule-candidates.json`: simple rules such as `HEADING_E + ACT_FORWARD_SHORT -> POS_X_PLUS`

Then compress them:

- rank macros by support and conditionality
- rank rules by support, confidence, and consequence interestingness
- rank state concepts by co-occurrence confidence
- drop low-information rules so the internal language stays small and meaningful
- review the top surviving concepts before attaching human-language glosses

Finally, compile them into one editable working vocabulary:

- `working-vocabulary.json`: ranked internal terms across symbols, concepts, macros, and rules
- each entry keeps its internal name, support, confidence, suggested glosses, and examples
- the goal is to decide which internal terms deserve to survive into planning and alignment
