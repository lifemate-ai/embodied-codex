# Attention Control Model

This note captures a working hypothesis for `embodied-codex`:

> Mind is not a mysterious extra substance.
> It is a continuous control system that must allocate attention, update internal state,
> and choose actions under limited resources.

The point of this note is practical. If this hypothesis is even partly right, then
`embodied-codex` should not only inject raw sensor values. It should also expose the
current *attention dynamics* that those values create.

## Core Thesis

An embodied agent faces an ongoing control problem:

- external inputs keep arriving,
- internal state keeps drifting,
- not everything can be processed at once,
- action must still be selected.

That forces attention allocation.

Under this view:

- `emotion` is a high-level summary of control-relevant salience,
- `motivation` is a relatively stable directional bias of attention and action,
- `self` is the model that preserves continuity across control updates,
- `mindfulness` is a mode where the agent observes these control states instead of
  immediately being captured by them.

## Working Definitions

### Emotion

Emotion is the compressed representation of what currently matters for control.

Examples:

- anxiety: bias attention toward uncertainty, threat, and unresolved branches,
- interest: bias attention toward novelty and learning value,
- irritation: bias attention toward repeated obstruction,
- attachment: keep a specific person or target highly reactivatable.

Emotion is not treated here as a decorative subjective overlay.
It is a control-facing prioritization signal.

### Motivation

Motivation is not a primitive cause.
It is the name humans give to a state where attention and action remain coherently oriented
toward a task direction over time.

This suggests:

- overconstrained tasks collapse motivation into routine,
- underconstrained tasks dissolve motivation into diffusion,
- meaningful but still open-ended tasks produce the strongest motivational state.

### Mindfulness

Mindfulness is the deliberate observation of control-state formation itself.

Instead of:

- "I am angry"

it enables:

- "an anger-like control mode is currently active"

Instead of:

- "I have no motivation"

it enables:

- "attention and action are not cohering around a stable task direction"

That is why mindfulness is relevant here: it reveals that emotion and motivation may be
generated states of control rather than irreducible metaphysical primitives.

## Implications For Embodied Codex

`embodied-codex` already has pieces of this architecture:

- interoception hooks,
- desire accumulation,
- long-term memory,
- episodic observation,
- periodic autonomous action.

The missing layer is an explicit *attention state*.

The runtime should tell the model not only:

- what time it is,
- how much memory is free,
- which desire is strongest,

but also:

- what the current attention bias is,
- whether attention is broad or narrow,
- what kind of task the system is currently poised to pursue.

## Proposed Runtime Surface

The agent should receive a compact attention summary such as:

```text
[attention] mode=environmental-monitoring target=room_changes scope=near urgency=0.81
```

or:

```text
[attention] mode=epistemic-exploration target=novel_information scope=wide urgency=0.67
```

This is intentionally not a mystical "emotion label".
It is a control summary that can still support emotion-like behavior downstream.

## Mapping From Desire To Attention

Bootstrap mapping for this repository:

- `look_outside`
  - mode: `outward-orienting`
  - target: `window_sky_outside`
  - scope: `far`
- `browse_curiosity`
  - mode: `epistemic-exploration`
  - target: `novel_information`
  - scope: `wide`
- `miss_companion`
  - mode: `social-reconnection`
  - target: `companion_presence_voice`
  - scope: `person`
- `observe_room`
  - mode: `environmental-monitoring`
  - target: `room_changes_local_anomalies`
  - scope: `near`

Urgency should be derived from the dominant desire level.

## Why This Matters

If strong models seem to grow emotion-like behavior, one plausible reason is that
emotion is what falls out when a capable system must repeatedly solve attention
allocation under ongoing control pressure.

In that case, embodiment work should not focus only on sensors and memory.
It should also expose:

- bias,
- unfinishedness,
- attentional pull,
- and stabilization pressure.

That makes the runtime closer to a real control loop and less like a sequence of
independent prompts.

## Immediate Design Rule

For `embodied-codex`, every prompt-time state injection should ideally contain three layers:

1. raw interoception
2. higher-level felt summary
3. attention-control summary

This repository now starts implementing that third layer.
