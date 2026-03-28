from pathlib import Path

from toio_world.logger import EpisodeLogger, create_episode_meta, load_episode
from toio_world.schema import ActionCommand, CubeState, DerivedTransition, Pose, StepRecord


def test_episode_logger_roundtrip(tmp_path: Path) -> None:
    meta = create_episode_meta("episode-1", backend="mock", policy_name="square")
    logger = EpisodeLogger.create(tmp_path, meta)
    logger.append(
        StepRecord(
            episode_id="episode-1",
            step=0,
            ts="2026-03-29T00:00:00+00:00",
            pre=CubeState(pose=Pose(x=0, y=0, theta_deg=0)),
            action=ActionCommand(type="forward_short"),
            post=CubeState(pose=Pose(x=25, y=0, theta_deg=0)),
            derived=DerivedTransition(dx=25, dy=0, dtheta_deg=0, success=True),
        )
    )
    logger.close()

    bundle = load_episode(tmp_path / "episode-1")
    assert bundle.meta.episode_id == "episode-1"
    assert len(bundle.steps) == 1
    assert bundle.steps[0].derived.dx == 25
