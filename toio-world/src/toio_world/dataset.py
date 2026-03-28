from __future__ import annotations

from pydantic import BaseModel

from .schema import StepRecord


class NextPoseExample(BaseModel):
    action_type: str
    pre_x: float
    pre_y: float
    pre_theta_deg: float
    target_dx: float
    target_dy: float
    target_dtheta_deg: float


def to_next_pose_examples(steps: list[StepRecord]) -> list[NextPoseExample]:
    examples: list[NextPoseExample] = []
    for step in steps:
        pre_pose = step.pre.pose
        derived = step.derived
        if (
            pre_pose.x is None
            or pre_pose.y is None
            or pre_pose.theta_deg is None
            or derived.dx is None
            or derived.dy is None
            or derived.dtheta_deg is None
        ):
            continue
        examples.append(
            NextPoseExample(
                action_type=step.action.type,
                pre_x=pre_pose.x,
                pre_y=pre_pose.y,
                pre_theta_deg=pre_pose.theta_deg,
                target_dx=derived.dx,
                target_dy=derived.dy,
                target_dtheta_deg=derived.dtheta_deg,
            )
        )
    return examples
