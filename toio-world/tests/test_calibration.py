from toio_world.calibration import build_calibration_sequence, fit_action_calibration_profile
from toio_world.schema import (
    ActionCommand,
    CubeState,
    DerivedTransition,
    EpisodeBundle,
    EpisodeMeta,
    Pose,
    StepRecord,
)


def test_build_calibration_sequence_repeats_each_action() -> None:
    sequence = build_calibration_sequence(repeats=2)
    assert sequence[:2] == ["forward_short", "forward_short"]
    assert sequence[-2:] == ["turn_right_large", "turn_right_large"]
    assert len(sequence) == 14


def test_fit_action_calibration_profile_summarizes_action_stats() -> None:
    bundle = EpisodeBundle(
        meta=EpisodeMeta(
            episode_id="cal-e1",
            created_at="2026-03-29T00:00:00+00:00",
            backend="mock",
            policy_name="calibration_sweep",
        ),
        steps=[
            StepRecord(
                episode_id="cal-e1",
                step=0,
                ts="2026-03-29T00:00:00+00:00",
                pre=CubeState(pose=Pose(x=0, y=0, theta_deg=0)),
                action=ActionCommand(type="forward_short"),
                post=CubeState(pose=Pose(x=24, y=0, theta_deg=0)),
                derived=DerivedTransition(dx=24, dy=0, dtheta_deg=0, success=True),
            ),
            StepRecord(
                episode_id="cal-e1",
                step=1,
                ts="2026-03-29T00:00:01+00:00",
                pre=CubeState(pose=Pose(x=24, y=0, theta_deg=0)),
                action=ActionCommand(type="forward_short"),
                post=CubeState(pose=Pose(x=49, y=1, theta_deg=0)),
                derived=DerivedTransition(dx=25, dy=1, dtheta_deg=0, success=True),
            ),
            StepRecord(
                episode_id="cal-e1",
                step=2,
                ts="2026-03-29T00:00:02+00:00",
                pre=CubeState(pose=Pose(x=49, y=1, theta_deg=0)),
                action=ActionCommand(type="turn_left_small"),
                post=CubeState(pose=Pose(x=49, y=1, theta_deg=31)),
                derived=DerivedTransition(dx=0, dy=0, dtheta_deg=31, success=True),
            ),
        ],
    )
    profile = fit_action_calibration_profile([bundle])
    by_action = {item.action_type: item for item in profile.actions}
    assert by_action["forward_short"].count == 2
    assert by_action["forward_short"].mean_dx == 24.5
    assert by_action["forward_short"].suggested_scalar == 24.51
    assert by_action["turn_left_small"].mean_dtheta_deg == 31.0
    assert by_action["turn_left_small"].suggested_scalar == 31.0
