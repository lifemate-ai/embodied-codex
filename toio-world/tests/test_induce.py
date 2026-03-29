from toio_world.induce import derive_symbolized_steps
from toio_world.schema import (
    ActionCommand,
    CubeState,
    DerivedTransition,
    EpisodeBundle,
    EpisodeMeta,
    MarkerObservation,
    Pose,
    StepRecord,
)


def test_derive_symbolized_steps_marks_heading_action_and_change() -> None:
    bundle = EpisodeBundle(
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
                pre=CubeState(
                    pose=Pose(x=0, y=0, theta_deg=0),
                    marker=MarkerObservation(kind="position_id", marker_id="origin"),
                ),
                action=ActionCommand(type="forward_short"),
                post=CubeState(
                    pose=Pose(x=25, y=0, theta_deg=0),
                    marker=MarkerObservation(kind="position_id", marker_id="1"),
                ),
                derived=DerivedTransition(dx=25, dy=0, dtheta_deg=0, success=True),
            )
        ],
    )
    observations = derive_symbolized_steps(bundle)
    assert len(observations) == 1
    item = observations[0]
    assert "HEADING_E" in item.pre_state_symbols
    assert item.action_symbol == "ACT_FORWARD_SHORT"
    assert "MOVE_SMALL" in item.change_symbols
    assert "ROT_NONE" in item.change_symbols
