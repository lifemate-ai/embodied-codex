from __future__ import annotations

import json
from pathlib import Path

import typer
from rich import print

from .align import save_gloss_table
from .baseline import evaluate_mean_delta_model, fit_mean_delta_model, save_mean_delta_model
from .calibration import fit_action_calibration_profile
from .concepts import discover_state_concepts
from .config import load_policy_config, load_world_config
from .controller import MockController, ToioController
from .dataset import to_next_pose_examples
from .discover import discover_action_macros, mine_transition_rules
from .induce import derive_symbolized_steps, symbol_counts
from .logger import EpisodeLogger, create_episode_meta, load_episode
from .policies import build_policy
from .protolang import PrimitiveSymbolConfig
from .replay import replay_steps
from .review import review_protolang
from .schema import CubeState, DerivedTransition, StepRecord, now_iso
from .visualize import episode_summary
from .vocabulary import compile_episode_vocabulary

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _controller_for_backend(backend: str):
    if backend == "mock":
        return MockController()
    if backend == "toio":
        return ToioController()
    raise typer.BadParameter(f"Unsupported backend: {backend}")


def _derive(pre: CubeState, post: CubeState) -> DerivedTransition:
    pre_pose = pre.pose
    post_pose = post.pose
    if (
        pre_pose.x is None
        or pre_pose.y is None
        or pre_pose.theta_deg is None
        or post_pose.x is None
        or post_pose.y is None
        or post_pose.theta_deg is None
    ):
        return DerivedTransition(success=False)
    return DerivedTransition(
        dx=round(post_pose.x - pre_pose.x, 3),
        dy=round(post_pose.y - pre_pose.y, 3),
        dtheta_deg=round(post_pose.theta_deg - pre_pose.theta_deg, 3),
        success=True,
    )


@app.command("collect-pattern")
def collect_pattern(
    policy_name: str = typer.Argument(..., help="square, spin, random_walk"),
    episode_root: Path = typer.Option(Path("episodes")),
    backend: str = typer.Option("mock"),
    repeats: int = typer.Option(1, help="Policy repeat count where applicable"),
    steps: int = typer.Option(32, help="Random walk steps"),
    world_config: Path = typer.Option(Path("configs/world.toml")),
    policy_config: Path = typer.Option(Path("configs/policies.toml")),
) -> None:
    world = load_world_config(world_config)
    policies = load_policy_config(policy_config)
    episode_root = episode_root if str(episode_root) != "episodes" else Path(world.episode_root)
    backend = backend if backend != "mock" else world.controller_backend
    episode_id = f"{policy_name}-{now_iso().replace(':', '-').replace('+', '_')}"
    policy_defaults: dict[str, int] = {}
    if policy_name == "random_walk":
        policy_defaults = {
            "steps": steps if steps != 32 else policies.random_walk.steps,
            "seed": policies.random_walk.seed,
        }
    elif policy_name == "square":
        policy_defaults = {"repeats": repeats if repeats != 1 else policies.square.side_repeats}
    elif policy_name == "spin":
        policy_defaults = {"repeats": repeats if repeats != 1 else policies.spin.repeats}
    meta = create_episode_meta(
        episode_id,
        backend=backend,
        policy_name=policy_name,
        tags=["bootstrap", "pattern"],
        config_paths={
            "world": str(world_config),
            "policies": str(policy_config),
        },
    )
    logger = EpisodeLogger.create(episode_root=episode_root, meta=meta)
    controller = _controller_for_backend(backend)
    actions = build_policy(policy_name, **policy_defaults)

    controller.connect()
    try:
        for index, action in enumerate(actions):
            pre = controller.read_state()
            post = controller.apply_action(action)
            logger.append(
                StepRecord(
                    episode_id=episode_id,
                    step=index,
                    ts=now_iso(),
                    pre=pre,
                    action=action,
                    post=post,
                    derived=_derive(pre, post),
                )
            )
    finally:
        controller.disconnect()
        logger.close()

    print(f"[green]wrote[/green] {logger.episode_dir}")


@app.command("collect-calibration")
def collect_calibration(
    episode_root: Path = typer.Option(Path("episodes")),
    backend: str = typer.Option("mock"),
    repeats: int = typer.Option(8, help="How many times to repeat each discrete action"),
    world_config: Path = typer.Option(Path("configs/world.toml")),
) -> None:
    world = load_world_config(world_config)
    episode_root = episode_root if str(episode_root) != "episodes" else Path(world.episode_root)
    backend = backend if backend != "mock" else world.controller_backend
    episode_id = f"calibration-{now_iso().replace(':', '-').replace('+', '_')}"
    meta = create_episode_meta(
        episode_id,
        backend=backend,
        policy_name="calibration_sweep",
        tags=["bootstrap", "calibration"],
        notes="Repeated discrete action sweep for action-profile fitting.",
        config_paths={"world": str(world_config)},
    )
    logger = EpisodeLogger.create(episode_root=episode_root, meta=meta)
    controller = _controller_for_backend(backend)
    actions = build_policy("calibration_sweep", repeats=repeats)

    controller.connect()
    try:
        for index, action in enumerate(actions):
            pre = controller.read_state()
            post = controller.apply_action(action)
            logger.append(
                StepRecord(
                    episode_id=episode_id,
                    step=index,
                    ts=now_iso(),
                    pre=pre,
                    action=action,
                    post=post,
                    derived=_derive(pre, post),
                )
            )
    finally:
        controller.disconnect()
        logger.close()

    print(f"[green]wrote[/green] {logger.episode_dir}")


@app.command("inspect")
def inspect_episode(path: Path = typer.Argument(...)) -> None:
    bundle = load_episode(path)
    print(episode_summary(bundle))


@app.command("replay")
def replay_episode(
    path: Path = typer.Argument(...),
    backend: str = typer.Option("mock"),
) -> None:
    bundle = load_episode(path)
    states = replay_steps(_controller_for_backend(backend), bundle.steps)
    print(
        {
            "episode_id": bundle.meta.episode_id,
            "replayed_steps": len(states),
            "final_pose": states[-1].pose.model_dump(mode="json") if states else None,
        }
    )


@app.command("fit-baseline")
def fit_baseline(
    paths: list[Path] = typer.Argument(..., help="Episode directories to fit on"),
    output: Path = typer.Option(Path("baseline-next-pose.json")),
) -> None:
    bundles = [load_episode(path) for path in paths]
    model = fit_mean_delta_model(bundles)
    save_mean_delta_model(model, output)
    print(
        {
            "output": str(output),
            "episodes": model.episode_ids,
            "actions": sorted(model.action_means),
        }
    )


@app.command("eval-baseline")
def eval_baseline(
    model_path: Path = typer.Argument(...),
    paths: list[Path] = typer.Argument(..., help="Episode directories to evaluate on"),
) -> None:
    from .baseline import load_mean_delta_model

    model = load_mean_delta_model(model_path)
    examples = []
    for path in paths:
        examples.extend(to_next_pose_examples(load_episode(path).steps))
    print(evaluate_mean_delta_model(model, examples).model_dump(mode="json"))


@app.command("profile-actions")
def profile_actions(
    paths: list[Path] = typer.Argument(..., help="Episode directories to summarize"),
    output: Path = typer.Option(Path("action-profile.json")),
) -> None:
    bundles = [load_episode(path) for path in paths]
    profile = fit_action_calibration_profile(bundles)
    profile.save(output)
    print(
        {
            "output": str(output),
            "episodes": profile.episode_ids,
            "actions": [action.model_dump(mode="json") for action in profile.actions],
        }
    )


@app.command("derive-symbols")
def derive_symbols(
    path: Path = typer.Argument(...),
    output: Path | None = typer.Option(None),
    gloss_output: Path | None = typer.Option(None),
) -> None:
    bundle = load_episode(path)
    observations = derive_symbolized_steps(bundle, PrimitiveSymbolConfig())
    output_path = output or (path / "symbols.jsonl")
    with output_path.open("w", encoding="utf-8") as handle:
        for item in observations:
            handle.write(json.dumps(item.model_dump(mode="json"), ensure_ascii=True))
            handle.write("\n")
    if gloss_output is None:
        gloss_output = path / "gloss-table.json"
    save_gloss_table(observations, gloss_output)
    print(
        {
            "symbols_path": str(output_path),
            "gloss_path": str(gloss_output),
            "counts": symbol_counts(observations),
        }
    )


@app.command("discover-macros")
def discover_macros(
    path: Path = typer.Argument(...),
    output: Path | None = typer.Option(None),
    min_support: int = typer.Option(2),
    max_length: int = typer.Option(2),
    state_conditioned: bool = typer.Option(True),
) -> None:
    bundle = load_episode(path)
    observations = derive_symbolized_steps(bundle, PrimitiveSymbolConfig())
    catalog = discover_action_macros(
        observations,
        min_support=min_support,
        max_length=max_length,
        state_conditioned=state_conditioned,
    )
    output_path = output or (path / "macro-candidates.json")
    catalog.save(output_path)
    print(
        {
            "macro_path": str(output_path),
            "count": len(catalog.macros),
            "top_names": [macro.name for macro in catalog.macros[:5]],
        }
    )


@app.command("mine-rules")
def mine_rules(
    path: Path = typer.Argument(...),
    output: Path | None = typer.Option(None),
    min_support: int = typer.Option(2),
    min_confidence: float = typer.Option(0.8),
    drop_low_value: bool = typer.Option(True),
    max_state_arity: int = typer.Option(2),
) -> None:
    bundle = load_episode(path)
    observations = derive_symbolized_steps(bundle, PrimitiveSymbolConfig())
    catalog = mine_transition_rules(
        observations,
        min_support=min_support,
        min_confidence=min_confidence,
        drop_low_value=drop_low_value,
        max_state_arity=max_state_arity,
    )
    output_path = output or (path / "rule-candidates.json")
    catalog.save(output_path)
    print(
        {
            "rule_path": str(output_path),
            "count": len(catalog.rules),
            "top_rules": [rule.model_dump(mode="json") for rule in catalog.rules[:5]],
        }
    )


@app.command("discover-concepts")
def discover_concepts(
    path: Path = typer.Argument(...),
    output: Path | None = typer.Option(None),
    min_support: int = typer.Option(2),
    min_confidence: float = typer.Option(0.8),
    max_size: int = typer.Option(2),
) -> None:
    bundle = load_episode(path)
    observations = derive_symbolized_steps(bundle, PrimitiveSymbolConfig())
    catalog = discover_state_concepts(
        observations,
        min_support=min_support,
        min_confidence=min_confidence,
        max_size=max_size,
    )
    output_path = output or (path / "concept-candidates.json")
    catalog.save(output_path)
    print(
        {
            "concept_path": str(output_path),
            "count": len(catalog.concepts),
            "top_names": [concept.name for concept in catalog.concepts[:5]],
        }
    )


@app.command("review-protolang")
def review_proto_language(
    path: Path = typer.Argument(...),
    top_k: int = typer.Option(10),
    max_state_arity: int = typer.Option(2),
) -> None:
    print(review_protolang(path, top_k=top_k, max_state_arity=max_state_arity))


@app.command("compile-vocabulary")
def compile_vocabulary(
    path: Path = typer.Argument(...),
    output: Path | None = typer.Option(None),
    top_k_per_kind: int = typer.Option(10),
    max_state_arity: int = typer.Option(2),
) -> None:
    vocabulary = compile_episode_vocabulary(
        path,
        top_k_per_kind=top_k_per_kind,
        max_state_arity=max_state_arity,
    )
    output_path = output or (path / "working-vocabulary.json")
    vocabulary.save(output_path)
    print(
        {
            "vocabulary_path": str(output_path),
            "stats": vocabulary.stats,
            "top_entries": [entry.model_dump(mode="json") for entry in vocabulary.entries[:10]],
        }
    )


def main() -> None:
    app()
