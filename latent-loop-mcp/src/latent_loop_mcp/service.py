"""Service layer for latent-loop-mcp."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from .config import LatentLoopConfig
from .diagnostics import candidate_jaccard_delta, iteration_quality_score, novelty_score
from .distribution import (
    distribution_from_candidates,
    entropy,
    kl_divergence,
    normalized_entropy,
    representative_candidates,
    top_candidate_key,
    top_margin,
)
from .fact_graph import compose_path
from .halting import evaluate_halting
from .models import Candidate, FactEdge, HaltingMetrics, IterationRecord, LoopState, OpenSubgoal, utc_now
from .store import LatentLoopStore


class LatentLoopService:
    """Business logic for latent-loop-mcp."""

    def __init__(self, config: LatentLoopConfig, store: LatentLoopStore):
        self.config = config
        self.store = store

    def start_loop(
        self,
        *,
        query: str,
        mode: str = "adaptive",
        min_iterations: int | None = None,
        max_iterations: int | None = None,
        complexity_hint: str = "unknown",
        initial_subgoals: list[str] | None = None,
    ) -> dict[str, Any]:
        subgoals = [
            OpenSubgoal(description=item, kind="retrieve_fact")
            for item in (initial_subgoals or [])
        ]
        state = LoopState(
            query=query,
            mode=mode if mode in {"fixed", "dynamic", "adaptive"} else self.config.default_mode,
            min_iterations=min_iterations or self.config.min_iterations,
            max_iterations=max_iterations or self.config.max_iterations,
            open_subgoals=subgoals,
            metadata={"complexity_hint": complexity_hint, "margin_history": [], "novelty_history": []},
        )
        self.store.create_loop(state)
        return {
            "loop_id": state.id,
            "decision": "CONTINUE",
            "iteration": 0,
            "loop_block_instruction": (
                "Read state, retrieve only necessary evidence, update 1-5 candidates, "
                "track subgoals, and commit the iteration."
            ),
        }

    def commit_iteration(
        self,
        *,
        loop_id: str,
        compact_trace: str,
        candidates: list[dict[str, Any]],
        facts_used: list[str] | None = None,
        facts_added: list[str] | None = None,
        open_subgoals: list[dict[str, Any] | str] | None = None,
        closed_subgoals: list[str] | None = None,
        contradictions: list[str] | None = None,
    ) -> dict[str, Any]:
        state = self.store.get_loop(loop_id)
        state.iteration += 1
        state.updated_at = utc_now()

        candidate_models = [Candidate.model_validate(candidate) for candidate in candidates]
        facts_used = facts_used or []
        facts_added = facts_added or []
        contradictions = contradictions or []

        distribution = distribution_from_candidates(candidate_models)
        metrics = HaltingMetrics(
            kl_delta=kl_divergence(distribution, state.previous_distribution),
            entropy=entropy(distribution),
            normalized_entropy=normalized_entropy(distribution),
            top_margin=top_margin(distribution),
            novelty=novelty_score(len(facts_used), len(facts_added)),
            candidate_jaccard_delta=candidate_jaccard_delta(distribution, state.previous_distribution),
        )

        state.candidates = candidate_models
        state.previous_distribution = distribution
        state.active_fact_ids = list(OrderedDict.fromkeys([*state.active_fact_ids, *facts_used, *facts_added]))
        state.summary_state = compact_trace
        state.user_visible_summary = compact_trace
        state.open_subgoals = self._merge_subgoals(
            state.open_subgoals,
            open_subgoals or [],
            closed_subgoals or [],
        )

        margin_history = list(state.metadata.get("margin_history", []))
        novelty_history = list(state.metadata.get("novelty_history", []))
        margin_history.append(metrics.top_margin)
        novelty_history.append(metrics.novelty)
        state.metadata["margin_history"] = margin_history[-10:]
        state.metadata["novelty_history"] = novelty_history[-10:]

        top_key = top_candidate_key(distribution)
        top_probability = distribution.get(top_key, 0.0) if top_key else 0.0
        decision = evaluate_halting(
            state,
            metrics,
            top_probability=top_probability,
            contradictions=contradictions,
            config=self.config,
        )

        record = IterationRecord(
            loop_id=loop_id,
            iteration=state.iteration,
            candidates=candidate_models,
            distribution=distribution,
            facts_used=facts_used,
            facts_added=facts_added,
            subgoals_opened=[subgoal.id for subgoal in state.open_subgoals if subgoal.status == "open"],
            subgoals_closed=[item for item in (closed_subgoals or [])],
            contradictions=contradictions,
            kl_delta=metrics.kl_delta,
            entropy=metrics.entropy,
            normalized_entropy=metrics.normalized_entropy,
            top_margin=metrics.top_margin,
            novelty=metrics.novelty,
            candidate_jaccard_delta=metrics.candidate_jaccard_delta,
            halt_decision=decision.decision,
            halt_reason=decision.reason,
            compact_trace=compact_trace,
        )

        quality_score = iteration_quality_score(
            top_probability=top_probability,
            top_margin=metrics.top_margin,
            normalized_entropy=metrics.normalized_entropy,
            novelty=metrics.novelty,
            contradictions=contradictions,
        )
        if state.best_iteration_score is None or quality_score > state.best_iteration_score:
            state.best_iteration_id = record.id
            state.best_iteration_score = quality_score

        self.store.add_iteration(record)
        self.store.update_loop(state)

        next_instruction = "Continue the same Loop Block."
        if decision.decision in {"HALT", "HALT_AT_BEST"}:
            next_instruction = f"Finalize using best_iteration_id={state.best_iteration_id}."
        elif decision.decision == "VERIFY":
            next_instruction = "Run a verification-focused iteration against the top candidate."
        elif decision.decision == "ASK_CLARIFY":
            next_instruction = "Ask the user a clarifying question before continuing."

        return {
            "loop_id": loop_id,
            "iteration": state.iteration,
            "decision": decision.decision,
            "reason": decision.reason,
            "metrics": decision.metrics.model_dump(mode="json"),
            "next_instruction": next_instruction,
        }

    def finalize_loop(self, *, loop_id: str) -> dict[str, Any]:
        state = self.store.get_loop(loop_id)
        record = None
        if state.best_iteration_id:
            record = self.store.get_iteration(state.best_iteration_id)
        if record is None:
            record = self.store.get_latest_iteration(loop_id)
        if record is None or not record.candidates:
            return {
                "answer": "",
                "confidence": 0.0,
                "best_iteration": None,
                "evidence_fact_ids": [],
                "compact_trace": "",
                "warning": "No candidates were recorded for this loop.",
            }

        top_key = top_candidate_key(record.distribution)
        representatives = representative_candidates(record.candidates)
        candidate = representatives[top_key] if top_key else max(record.candidates, key=lambda item: item.score)
        confidence = (
            candidate.confidence
            if candidate.confidence is not None
            else record.distribution.get(top_key or "", 0.0)
        )
        warning = ""
        if any(subgoal.status == "open" and subgoal.priority <= 2 for subgoal in state.open_subgoals):
            warning = "High-priority subgoals remain unresolved."
        elif confidence < self.config.confidence_threshold:
            warning = "Returned best available iteration under residual uncertainty."

        return {
            "answer": candidate.answer,
            "confidence": confidence,
            "best_iteration": record.iteration,
            "evidence_fact_ids": list(OrderedDict.fromkeys([*candidate.fact_ids, *record.facts_used])),
            "compact_trace": record.compact_trace,
            "warning": warning,
        }

    def get_loop_trace(self, *, loop_id: str, include_iterations: bool = True) -> dict[str, Any]:
        state = self.store.get_loop(loop_id)
        result: dict[str, Any] = {"state": state.model_dump(mode="json")}
        if include_iterations:
            result["iterations"] = [
                record.model_dump(mode="json") for record in self.store.list_iterations(loop_id)
            ]
        return result

    def upsert_fact(
        self,
        *,
        subject: str,
        relation: str,
        object: str,
        source: str,
        source_type: str,
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        edge = FactEdge(
            subject=subject,
            relation=relation,
            object=object,
            source=source,
            source_type=source_type,
            confidence=confidence,
            metadata=metadata or {},
        )
        stored = self.store.upsert_fact(edge)
        return {"fact_id": stored.id, "fact": stored.model_dump(mode="json")}

    def search_facts(
        self,
        *,
        subject: str | None = None,
        relation: str | None = None,
        object: str | None = None,
        query: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        return [
            fact.model_dump(mode="json")
            for fact in self.store.search_facts(
                subject=subject, relation=relation, object=object, query=query, limit=limit
            )
        ]

    def compose_path(
        self,
        *,
        start: str,
        relations: list[str],
        max_paths: int = 10,
        min_confidence: float | None = None,
    ) -> dict[str, Any]:
        paths = compose_path(
            self.store,
            start=start,
            relations=relations,
            max_paths=max_paths,
            min_confidence=min_confidence if min_confidence is not None else self.config.min_fact_confidence,
        )
        return {"paths": paths}

    def suggest_next_loop_action(self, *, loop_id: str) -> dict[str, Any]:
        state = self.store.get_loop(loop_id)
        if not state.candidates:
            return {
                "suggestion": "retrieve_memory",
                "instruction": f"Call memory.recall_with_associations with context: {state.query}",
                "why": "No viable candidates yet; retrieve relevant memories first.",
            }

        open_social = next(
            (
                subgoal
                for subgoal in state.open_subgoals
                if subgoal.status == "open"
                and subgoal.kind in {"retrieve_social_state", "resolve_reference", "check_boundary", "self_consistency"}
            ),
            None,
        )
        if open_social is not None:
            return {
                "suggestion": "retrieve_social_context",
                "instruction": (
                    "Call sociality.summarize_social_context / get_person_model / "
                    "get_current_joint_focus as needed for: "
                    f"{open_social.description}"
                ),
                "why": "The remaining ambiguity is social rather than purely factual.",
            }

        open_compose = next(
            (subgoal for subgoal in state.open_subgoals if subgoal.status == "open" and subgoal.kind == "compose_path"),
            None,
        )
        if open_compose is not None:
            return {
                "suggestion": "compose_path",
                "instruction": f"Use latent-loop.compose_path to resolve: {open_compose.description}",
                "why": "A multi-hop fact composition subgoal remains open.",
            }

        open_verify = next(
            (
                subgoal
                for subgoal in state.open_subgoals
                if subgoal.status == "open" and subgoal.kind == "verify_candidate"
            ),
            None,
        )
        if open_verify is not None:
            return {
                "suggestion": "verify_candidate",
                "instruction": f"Probe contradictions or missing evidence for: {open_verify.description}",
                "why": "A verification pass is the highest-value next action.",
            }

        return {
            "suggestion": "search_facts",
            "instruction": f"Call latent-loop.search_facts with query: {state.query}",
            "why": "Additional structured evidence may improve stability before halting.",
        }

    def get_loop_stats(self) -> dict[str, Any]:
        return self.store.get_stats()

    @staticmethod
    def _merge_subgoals(
        existing: list[OpenSubgoal],
        new_items: list[dict[str, Any] | str],
        closed_items: list[str],
    ) -> list[OpenSubgoal]:
        merged: OrderedDict[str, OpenSubgoal] = OrderedDict((subgoal.id, subgoal) for subgoal in existing)
        for item in new_items:
            if isinstance(item, str):
                subgoal = OpenSubgoal(description=item)
            else:
                payload = dict(item)
                if "description" not in payload:
                    raise ValueError("Subgoal objects must include description.")
                subgoal = OpenSubgoal.model_validate(payload)
            merged[subgoal.id] = subgoal

        closed_keys = set(closed_items)
        for subgoal_id, subgoal in list(merged.items()):
            if subgoal_id in closed_keys or subgoal.description in closed_keys:
                merged[subgoal_id] = subgoal.model_copy(update={"status": "done"})
        return list(merged.values())
