from toio_world.dataset import to_next_pose_examples
from toio_world.schema import (
    ActionCommand,
    CubeState,
    DerivedTransition,
    Pose,
    StepRecord,
)


def test_to_next_pose_examples_extracts_targets() -> None:
    examples = to_next_pose_examples(
        [
            StepRecord(
                episode_id="e1",
                step=0,
                ts="2026-03-29T00:00:00+00:00",
                pre=CubeState(pose=Pose(x=0, y=0, theta_deg=0)),
                action=ActionCommand(type="forward_short"),
                post=CubeState(pose=Pose(x=25, y=0, theta_deg=0)),
                derived=DerivedTransition(dx=25, dy=0, dtheta_deg=0, success=True),
            )
        ]
    )
    assert len(examples) == 1
    assert examples[0].action_type == "forward_short"
    assert examples[0].target_dx == 25
