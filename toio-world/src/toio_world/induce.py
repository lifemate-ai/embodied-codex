from __future__ import annotations

import math
from collections import Counter

from .protolang import PrimitiveSymbolConfig, SymbolizedStep
from .schema import EpisodeBundle, Pose, StepRecord


def _heading_symbol(theta_deg: float | None) -> str | None:
    if theta_deg is None:
        return None
    theta = theta_deg % 360.0
    if 45 <= theta < 135:
        return "HEADING_N"
    if 135 <= theta < 225:
        return "HEADING_W"
    if 225 <= theta < 315:
        return "HEADING_S"
    return "HEADING_E"


def _bin_symbol(value: float | None, low: float, high: float, prefix: str) -> str | None:
    if value is None:
        return None
    if math.isclose(low, high):
        return f"{prefix}_CENTER"
    ratio = (value - low) / (high - low)
    if ratio < 0.33:
        return f"{prefix}_LOW"
    if ratio < 0.66:
        return f"{prefix}_MID"
    return f"{prefix}_HIGH"


def _edge_symbols(
    pose: Pose,
    *,
    min_x: float,
    max_x: float,
    min_y: float,
    max_y: float,
    config: PrimitiveSymbolConfig,
) -> list[str]:
    symbols: list[str] = []
    if pose.x is None or pose.y is None:
        return symbols
    margin_x = (max_x - min_x) * config.edge_margin_ratio
    margin_y = (max_y - min_y) * config.edge_margin_ratio
    if pose.x <= min_x + margin_x:
        symbols.append("NEAR_EDGE_X_MIN")
    if pose.x >= max_x - margin_x:
        symbols.append("NEAR_EDGE_X_MAX")
    if pose.y <= min_y + margin_y:
        symbols.append("NEAR_EDGE_Y_MIN")
    if pose.y >= max_y - margin_y:
        symbols.append("NEAR_EDGE_Y_MAX")
    return symbols


def _state_symbols(
    pose: Pose,
    marker_id: str | None,
    *,
    min_x: float,
    max_x: float,
    min_y: float,
    max_y: float,
    config: PrimitiveSymbolConfig,
) -> list[str]:
    symbols: list[str] = []
    heading = _heading_symbol(pose.theta_deg)
    if heading:
        symbols.append(heading)
    x_bin = _bin_symbol(pose.x, min_x, max_x, "X")
    y_bin = _bin_symbol(pose.y, min_y, max_y, "Y")
    if x_bin:
        symbols.append(x_bin)
    if y_bin:
        symbols.append(y_bin)
    symbols.extend(
        _edge_symbols(
            pose,
            min_x=min_x,
            max_x=max_x,
            min_y=min_y,
            max_y=max_y,
            config=config,
        )
    )
    if marker_id:
        symbols.append(f"MARKER_{marker_id}")
    return symbols


def _action_symbol(action_type: str) -> str:
    return f"ACT_{action_type.upper()}"


def _change_symbols(step: StepRecord, config: PrimitiveSymbolConfig) -> list[str]:
    symbols: list[str] = []
    dx = step.derived.dx or 0.0
    dy = step.derived.dy or 0.0
    dtheta = step.derived.dtheta_deg or 0.0
    distance = math.hypot(dx, dy)

    if distance < config.movement_fail_threshold:
        symbols.append("MOVE_FAIL")
    elif distance < config.movement_large_threshold:
        symbols.append("MOVE_SMALL")
    else:
        symbols.append("MOVE_LARGE")

    if dx > config.movement_fail_threshold:
        symbols.append("POS_X_PLUS")
    elif dx < -config.movement_fail_threshold:
        symbols.append("POS_X_MINUS")

    if dy > config.movement_fail_threshold:
        symbols.append("POS_Y_PLUS")
    elif dy < -config.movement_fail_threshold:
        symbols.append("POS_Y_MINUS")

    if dtheta > config.rotation_threshold_deg:
        symbols.append("ROT_LEFT")
    elif dtheta < -config.rotation_threshold_deg:
        symbols.append("ROT_RIGHT")
    else:
        symbols.append("ROT_NONE")

    if step.derived.success:
        symbols.append("TRANSITION_VALID")
    else:
        symbols.append("TRANSITION_UNKNOWN")
    return symbols


def derive_symbolized_steps(
    bundle: EpisodeBundle,
    config: PrimitiveSymbolConfig | None = None,
) -> list[SymbolizedStep]:
    config = config or PrimitiveSymbolConfig()
    poses = [pose for step in bundle.steps for pose in (step.pre.pose, step.post.pose)]
    xs = [pose.x for pose in poses if pose.x is not None]
    ys = [pose.y for pose in poses if pose.y is not None]
    min_x = min(xs, default=0.0)
    max_x = max(xs, default=0.0)
    min_y = min(ys, default=0.0)
    max_y = max(ys, default=0.0)

    observations: list[SymbolizedStep] = []
    for step in bundle.steps:
        observations.append(
            SymbolizedStep(
                episode_id=step.episode_id,
                step=step.step,
                ts=step.ts,
                pre_state_symbols=_state_symbols(
                    step.pre.pose,
                    step.pre.marker.marker_id,
                    min_x=min_x,
                    max_x=max_x,
                    min_y=min_y,
                    max_y=max_y,
                    config=config,
                ),
                action_symbol=_action_symbol(step.action.type),
                change_symbols=_change_symbols(step, config),
                post_state_symbols=_state_symbols(
                    step.post.pose,
                    step.post.marker.marker_id,
                    min_x=min_x,
                    max_x=max_x,
                    min_y=min_y,
                    max_y=max_y,
                    config=config,
                ),
            )
        )
    return observations


def symbol_counts(observations: list[SymbolizedStep]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for item in observations:
        counter.update(item.pre_state_symbols)
        counter.update([item.action_symbol])
        counter.update(item.change_symbols)
        counter.update(item.post_state_symbols)
    return dict(counter.most_common())
