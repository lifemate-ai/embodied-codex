# Latent Loop Benchmarks

This directory contains lightweight benchmarks for the symbolic and mocked-loop parts of
`latent-loop-mcp`.

## Symbolic graph benchmark

```bash
uv run python benchmarks/latent_loop/run_eval.py --entities 50 --relations 6 --max-hop 6 --mode symbolic
```

This checks deterministic multi-hop composition over a synthetic permutation graph.

## Mocked loop benchmark

```bash
uv run python benchmarks/latent_loop/run_eval.py --entities 50 --relations 6 --max-hop 6 --mode mocked-loop
```

This simulates shallower vs deeper tasks to ensure iteration counts and halt types move in the
expected direction.
