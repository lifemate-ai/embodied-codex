"""Run lightweight latent-loop benchmarks."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LATENT_LOOP_SRC = REPO_ROOT / "latent-loop-mcp" / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(LATENT_LOOP_SRC) not in sys.path:
    sys.path.insert(0, str(LATENT_LOOP_SRC))

from latent_loop_mcp.config import LatentLoopConfig
from latent_loop_mcp.fact_graph import compose_path
from latent_loop_mcp.models import FactEdge
from latent_loop_mcp.service import LatentLoopService
from latent_loop_mcp.store import LatentLoopStore
from benchmarks.latent_loop.synthetic_kg import build_synthetic_kg, relation_sequence_answer


def build_config(db_path: str) -> LatentLoopConfig:
    return LatentLoopConfig(
        db_path=db_path,
        default_mode="adaptive",
        min_iterations=2,
        max_iterations=8,
        kl_threshold=0.03,
        entropy_threshold=0.35,
        margin_threshold=0.25,
        novelty_threshold=0.05,
        confidence_threshold=0.72,
        overthinking_patience=2,
        allow_halt_with_unresolved_low_priority=True,
        store_compact_traces=True,
        store_private_cot=False,
        min_fact_confidence=0.0,
        allow_inferred_facts=True,
        prefer_atomic_facts=True,
        deduplicate_facts=True,
        max_paths=10,
    )


def run_symbolic_eval(entities: int, relations: int, max_hop: int) -> dict[str, object]:
    kg = build_synthetic_kg(entities, relations)
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = str(Path(temp_dir) / "latent_loop.db")
        store = LatentLoopStore(db_path)
        try:
            for relation, mapping in kg.relation_maps.items():
                for subject, obj in mapping.items():
                    store.upsert_fact(
                        FactEdge(
                            subject=subject,
                            relation=relation,
                            object=obj,
                            source="synthetic",
                            source_type="test",
                        )
                    )

            results: list[dict[str, object]] = []
            for hop in range(2, max_hop + 1):
                relation_sequence = [f"r{index % relations}" for index in range(hop)]
                start = "e0"
                expected = relation_sequence_answer(kg, start, relation_sequence)
                paths = compose_path(store, start=start, relations=relation_sequence, max_paths=3, min_confidence=0.0)
                actual = paths[0]["entities"][-1] if paths else None
                results.append({"hop": hop, "correct": actual == expected})
        finally:
            store.close()

    accuracy = sum(1 for item in results if item["correct"]) / len(results)
    return {"mode": "symbolic", "results": results, "accuracy": accuracy}


def run_mocked_loop_eval(max_hop: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as temp_dir:
        config = build_config(str(Path(temp_dir) / "latent_loop.db"))
        store = LatentLoopStore(config.db_path)
        service = LatentLoopService(config, store)
        try:
            results: list[dict[str, object]] = []
            for hop in range(2, max_hop + 1):
                loop = service.start_loop(query=f"mocked-hop-{hop}")
                for index in range(1, min(config.max_iterations, hop) + 1):
                    score = float(index)
                    result = service.commit_iteration(
                        loop_id=loop["loop_id"],
                        compact_trace=f"iteration {index}",
                        candidates=[{"answer": f"hop-{hop}", "score": score, "confidence": min(0.4 + 0.1 * index, 0.95)}],
                    )
                    if result["decision"] in {"HALT", "HALT_AT_BEST"}:
                        break
                stats = service.finalize_loop(loop_id=loop["loop_id"])
                results.append({"hop": hop, "best_iteration": stats["best_iteration"], "warning": stats["warning"]})
        finally:
            store.close()

    return {"mode": "mocked-loop", "results": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entities", type=int, default=50)
    parser.add_argument("--relations", type=int, default=6)
    parser.add_argument("--max-hop", type=int, default=6)
    parser.add_argument("--mode", choices=["symbolic", "mocked-loop"], default="symbolic")
    args = parser.parse_args()

    if args.mode == "symbolic":
        payload = run_symbolic_eval(args.entities, args.relations, args.max_hop)
    else:
        payload = run_mocked_loop_eval(args.max_hop)

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
