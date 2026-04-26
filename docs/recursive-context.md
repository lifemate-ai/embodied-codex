# Recursive Context MCP

`recursive-context-mcp` is the repository's RLM-style large-context layer.

The core idea is simple: a large context should live outside the prompt as files, directories, or
future database-backed manifests. The root agent then inspects that environment, extracts bounded
slices, asks focused sub-queries, and persists the resulting compact artifacts.

## Why It Exists

Embodied agents accumulate more context than a single prompt can hold:

- repository source trees,
- autonomous logs,
- memory exports,
- sociality traces,
- fixed-view camera observations,
- image annotation manifests,
- paper evaluation transcripts.

Flattening all of that into a prompt destroys structure and wastes tokens. A recursive context
workspace keeps the raw context inspectable and only lifts relevant slices into the active model
context.

## Relationship To Other MCP Servers

- `memory-mcp` stores durable memories and visual episodes.
- `sociality-mcp` performs social-state, relationship, boundary, and joint-attention reasoning.
- `latent-loop-mcp` manages recurrent-style candidate updates and halting.
- `recursive-context-mcp` manages large external contexts and bounded sub-query packets.

Together, they let Codex or Claude Code reason over large experience logs without pretending the
whole world fits in one context window.

## Privacy And Safety

The server stores explicit buffers, slices, sub-query packets, and program traces. It does not store
private chain-of-thought. If a context contains camera observations or personal logs, the caller is
responsible for redaction before sharing packets outside the local machine.

`run_program` is disabled by default. Enable it only for trusted local workflows with
`RECURSIVE_CONTEXT_ENABLE_PROGRAMS=true`; it is an inspection convenience, not a hardened sandbox.

## Good Uses

- Build a compact report from a large repository.
- Analyze one year of fixed-view observation metadata.
- Compare sociality ablation transcripts across multiple agents.
- Prepare sub-agent packets from only the files and line ranges that matter.
- Keep a trace of what evidence was inspected without exposing hidden reasoning.
