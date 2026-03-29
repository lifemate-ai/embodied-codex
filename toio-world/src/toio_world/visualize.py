from __future__ import annotations

from .schema import EpisodeBundle


def episode_summary(bundle: EpisodeBundle) -> dict[str, float | int | str]:
    total_dx = 0.0
    total_dy = 0.0
    total_dtheta = 0.0
    successes = 0
    for step in bundle.steps:
        total_dx += step.derived.dx or 0.0
        total_dy += step.derived.dy or 0.0
        total_dtheta += step.derived.dtheta_deg or 0.0
        if step.derived.success:
            successes += 1
    return {
        "episode_id": bundle.meta.episode_id,
        "policy_name": bundle.meta.policy_name,
        "steps": len(bundle.steps),
        "total_dx": round(total_dx, 3),
        "total_dy": round(total_dy, 3),
        "total_dtheta_deg": round(total_dtheta, 3),
        "success_rate": round(successes / len(bundle.steps), 3) if bundle.steps else 0.0,
    }
