from __future__ import annotations

import json
from pathlib import Path

from .schema import EpisodeBundle, EpisodeMeta, StepRecord, now_iso


def create_episode_meta(
    episode_id: str,
    *,
    backend: str,
    policy_name: str,
    notes: str = "",
    tags: list[str] | None = None,
    config_paths: dict[str, str] | None = None,
) -> EpisodeMeta:
    return EpisodeMeta(
        episode_id=episode_id,
        created_at=now_iso(),
        backend=backend,
        policy_name=policy_name,
        notes=notes,
        tags=tags or [],
        config_paths=config_paths or {},
    )


class EpisodeLogger:
    def __init__(self, episode_dir: Path, meta: EpisodeMeta) -> None:
        self.episode_dir = episode_dir
        self.meta = meta
        self._steps_path = episode_dir / "steps.jsonl"
        self._meta_path = episode_dir / "metadata.json"

    @classmethod
    def create(cls, episode_root: Path, meta: EpisodeMeta) -> "EpisodeLogger":
        episode_dir = episode_root / meta.episode_id
        episode_dir.mkdir(parents=True, exist_ok=False)
        logger = cls(episode_dir=episode_dir, meta=meta)
        logger._meta_path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")
        return logger

    def append(self, step: StepRecord) -> None:
        with self._steps_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(step.model_dump(mode="json"), ensure_ascii=True))
            handle.write("\n")

    def close(self) -> None:
        return None


def load_episode(path: str | Path) -> EpisodeBundle:
    episode_dir = Path(path)
    meta_path = episode_dir / "metadata.json"
    meta = EpisodeMeta.model_validate_json(meta_path.read_text(encoding="utf-8"))
    steps: list[StepRecord] = []
    with (episode_dir / "steps.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            steps.append(StepRecord.model_validate_json(line))
    return EpisodeBundle(meta=meta, steps=steps)
