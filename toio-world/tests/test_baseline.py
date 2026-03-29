from toio_world.baseline import evaluate_mean_delta_model, fit_mean_delta_model
from toio_world.dataset import to_next_pose_examples
from toio_world.schema import (
    ActionCommand,
    CubeState,
    DerivedTransition,
    EpisodeBundle,
    EpisodeMeta,
    Pose,
    StepRecord,
)


def _bundle() -> EpisodeBundle:
    return EpisodeBundle(
        meta=EpisodeMeta(
            episode_id="e1",
            created_at="2026-03-29T00:00:00+00:00",
            backend="mock",
            policy_name="square",
        ),
        steps=[
            StepRecord(
                episode_id="e1",
                step=0,
                ts="2026-03-29T00:00:00+00:00",
                pre=CubeState(pose=Pose(x=0, y=0, theta_deg=0)),
                action=ActionCommand(type="forward_short"),
                post=CubeState(pose=Pose(x=25, y=0, theta_deg=0)),
                derived=DerivedTransition(dx=25, dy=0, dtheta_deg=0, success=True),
            ),
            StepRecord(
                episode_id="e1",
                step=1,
                ts="2026-03-29T00:00:01+00:00",
                pre=CubeState(pose=Pose(x=25, y=0, theta_deg=0)),
                action=ActionCommand(type="forward_short"),
                post=CubeState(pose=Pose(x=50, y=0, theta_deg=0)),
                derived=DerivedTransition(dx=25, dy=0, dtheta_deg=0, success=True),
            ),
        ],
    )


def test_fit_and_eval_mean_delta_model() -> None:
    bundle = _bundle()
    model = fit_mean_delta_model([bundle])
    metrics = evaluate_mean_delta_model(model, to_next_pose_examples(bundle.steps))
    assert metrics.examples == 2
    assert metrics.mae_dx == 0.0
    assert metrics.mae_dy == 0.0
    assert metrics.mae_dtheta_deg == 0.0
