# Latent Loop

`latent-loop-mcp` is a software approximation of recurrent-depth reasoning for Embodied Codex.

It does not change the underlying model. Instead, Codex repeatedly applies the same reasoning
block to an external loop state that is stored in SQLite and can be inspected after the fact.

## Why It Exists

One-shot prompting is weak when the task needs:

- multi-hop composition
- long-term memory retrieval
- social interpretation
- joint attention or boundary checks
- verification before committing to an answer

The latent loop adds a control plane for those cases.

## Design

- `memory-mcp` remains the memory substrate
- `sociality-mcp` remains the social substrate
- `latent-loop-mcp` manages loop state, candidate distributions, fact edges, and halting
- Codex follows a repeated loop block defined in `AGENTS.md`

Each iteration leaves behind:

- the candidate distribution
- the facts used and added
- unresolved subgoals
- compact trace text
- halting metrics
- the decision to continue, verify, clarify, or halt

## Halting

The loop stops when one of these happens:

- distribution stabilizes and confidence is strong enough
- maximum iterations are reached
- later iterations are degrading without new evidence, so `HALT_AT_BEST` is returned
- the best available next step is to ask the user for clarification

Finalization returns the best iteration, not blindly the latest one.

## Fact Graph

Facts are stored atomically as `subject / relation / object` triples with provenance.

- atomic facts are preferred over storing only composed answers
- inferred facts must keep provenance
- inferred facts do not overwrite atomic facts
- `compose_path` performs deterministic multi-hop traversal

## Privacy

The loop is intentionally inspectable, but private hidden reasoning is not persisted.

Stored:

- compact traces
- candidates and scores
- evidence ids and fact ids
- halting metrics
- subgoals

Not stored:

- raw private chain-of-thought
- unnecessary private scene dumps
- secrets or credentials

## Failure Modes

- low novelty with degrading margin can trigger overthinking
- unresolved high-priority subgoals can block halting
- poor fact extraction can make the loop look stable while still being wrong
- social ambiguity can remain unresolved if `sociality-mcp` is never queried

## Recommended Use

Use the loop when a task is meaningfully harder than a single response and when the answer
benefits from inspectable intermediate state rather than opaque long prompting.
