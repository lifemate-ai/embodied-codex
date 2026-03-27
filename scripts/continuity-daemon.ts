import { mkdir, appendFile } from "node:fs/promises";
import { dirname } from "node:path";
import {
  ATTENTION_MAP,
  INTENTION_HINTS,
  loadDesireState,
  dominantDesire,
  type DesireName,
} from "./attention-lib";

const HOME_DIR = Bun.env.HOME ?? "";
const DEFAULT_CONTINUITY_DIR = HOME_DIR
  ? `${HOME_DIR}/.codex/continuity`
  : `${import.meta.dir}/../.continuity`;
const STATE_PATH =
  Bun.env.CODEX_CONTINUITY_STATE_PATH ??
  `${DEFAULT_CONTINUITY_DIR}/self_state.json`;
const EVENT_LOG_PATH =
  Bun.env.CODEX_CONTINUITY_EVENT_LOG_PATH ??
  `${DEFAULT_CONTINUITY_DIR}/events.jsonl`;
const INTEROCEPTION_STATE_PATH =
  Bun.env.CODEX_INTEROCEPTION_STATE_FILE ?? "/tmp/interoception_state.json";
function envNumber(value: string | undefined, fallback: number): number {
  const parsed = value ? Number.parseFloat(value) : Number.NaN;
  return Number.isFinite(parsed) ? parsed : fallback;
}

const TICK_INTERVAL_S = Math.max(
  1,
  envNumber(Bun.env.CODEX_CONTINUITY_TICK_SECONDS, 5),
);
const RECENT_EVENT_LIMIT = Math.max(
  1,
  Math.trunc(envNumber(Bun.env.CODEX_CONTINUITY_EVENT_LIMIT, 12)),
);

type ContinuityBand = "booting" | "fragile" | "forming" | "stable";
type WakeReason =
  | "none"
  | "cold-start"
  | "continuity-gap"
  | "prediction-miss"
  | "strong-drive";
type PredictionKey = "dominant_desire" | "attention_target" | "phase";
type EventKind = "tick" | "action" | "observation" | "note" | "rupture";

interface InteroceptionState {
  now?: {
    ts?: string;
    phase?: string;
    arousal?: number;
    mem_free?: number;
    thermal?: string | number;
    uptime_min?: number;
  };
  window?: unknown[];
}

interface ObservationSnapshot {
  at: string;
  phase: string | null;
  heartbeats: number | null;
  arousal: number | null;
  mem_free: number | null;
  dominant_desire: DesireName | null;
  dominant_level: number;
  attention_mode: string;
  attention_target: string;
  action_bias: string;
}

interface ContinuityPrediction {
  key: PredictionKey;
  expected: string;
  confidence: number;
  source: string;
  matched: boolean | null;
  observed: string | null;
}

interface ContinuityEvent {
  ts: string;
  kind: EventKind;
  source: string;
  detail: string;
  continuity_score?: number;
}

interface OwnershipState {
  last_action_at: string | null;
  last_action_source: string | null;
  last_action_detail: string | null;
  last_observation_at: string | null;
  last_observation_detail: string | null;
}

interface ContinuityState {
  schema_version: "1";
  kind: "continuity-self-state";
  updated_at: string;
  tick_interval_s: number;
  tick_count: number;
  continuity_score: number;
  continuity_band: ContinuityBand;
  continuity_note: string;
  last_tick_gap_s: number | null;
  rupture_flags: string[];
  should_wake: boolean;
  wake_reason: WakeReason;
  active_intentions: string[];
  predictions: ContinuityPrediction[];
  last_observation: ObservationSnapshot;
  ownership: OwnershipState;
  recent_events: ContinuityEvent[];
}

function round(value: number, digits = 3): number {
  return Number(value.toFixed(digits));
}

function clamp(value: number, min = 0, max = 1): number {
  return Math.min(max, Math.max(min, value));
}

function parseTimestamp(value: string | undefined): Date | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

async function ensureParent(path: string): Promise<void> {
  await mkdir(dirname(path), { recursive: true });
}

async function loadJsonFile<T>(path: string): Promise<T | null> {
  const file = Bun.file(path);
  if (!(await file.exists())) return null;
  try {
    return (await file.json()) as T;
  } catch {
    return null;
  }
}

async function loadState(): Promise<ContinuityState | null> {
  return loadJsonFile<ContinuityState>(STATE_PATH);
}

async function saveState(state: ContinuityState): Promise<void> {
  await ensureParent(STATE_PATH);
  await Bun.write(STATE_PATH, JSON.stringify(state, null, 2));
}

async function loadInteroceptionState(): Promise<InteroceptionState | null> {
  return loadJsonFile<InteroceptionState>(INTEROCEPTION_STATE_PATH);
}

async function loadRecentEvents(): Promise<ContinuityEvent[]> {
  const file = Bun.file(EVENT_LOG_PATH);
  if (!(await file.exists())) return [];

  try {
    const text = await file.text();
    return text
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .slice(-RECENT_EVENT_LIMIT)
      .flatMap((line) => {
        try {
          return [JSON.parse(line) as ContinuityEvent];
        } catch {
          return [];
        }
      });
  } catch {
    return [];
  }
}

async function appendEvent(event: ContinuityEvent): Promise<void> {
  await ensureParent(EVENT_LOG_PATH);
  await appendFile(EVENT_LOG_PATH, `${JSON.stringify(event)}\n`, "utf8");
}

function defaultObservation(now: Date): ObservationSnapshot {
  return {
    at: now.toISOString(),
    phase: null,
    heartbeats: null,
    arousal: null,
    mem_free: null,
    dominant_desire: null,
    dominant_level: 0,
    attention_mode: "maintenance",
    attention_target: "local_state",
    action_bias: "stabilize",
  };
}

function extractObservation(
  now: Date,
  interoception: InteroceptionState | null,
  dominant: ReturnType<typeof dominantDesire>,
): ObservationSnapshot {
  const base = defaultObservation(now);
  const profile = dominant ? ATTENTION_MAP[dominant.name] : null;
  return {
    at: interoception?.now?.ts ?? base.at,
    phase: interoception?.now?.phase ?? null,
    heartbeats: Array.isArray(interoception?.window)
      ? interoception!.window!.length
      : null,
    arousal:
      typeof interoception?.now?.arousal === "number"
        ? interoception.now.arousal
        : null,
    mem_free:
      typeof interoception?.now?.mem_free === "number"
        ? interoception.now.mem_free
        : null,
    dominant_desire: dominant?.name ?? null,
    dominant_level: dominant?.level ?? 0,
    attention_mode: profile?.mode ?? base.attention_mode,
    attention_target: profile?.target ?? base.attention_target,
    action_bias: profile?.actionBias ?? base.action_bias,
  };
}

function observedValue(
  key: PredictionKey,
  observation: ObservationSnapshot,
): string | null {
  switch (key) {
    case "dominant_desire":
      return observation.dominant_desire;
    case "attention_target":
      return observation.attention_target;
    case "phase":
      return observation.phase;
  }
}

function evaluatePredictions(
  previous: ContinuityPrediction[],
  observation: ObservationSnapshot,
): {
  evaluated: ContinuityPrediction[];
  matched: number;
  missed: number;
  total: number;
} {
  const evaluated = previous.map((prediction) => {
    const observed = observedValue(prediction.key, observation);
    return {
      ...prediction,
      observed,
      matched: observed === prediction.expected,
    };
  });

  return {
    evaluated,
    matched: evaluated.filter((item) => item.matched).length,
    missed: evaluated.filter((item) => item.matched === false).length,
    total: evaluated.length,
  };
}

function buildPredictions(
  observation: ObservationSnapshot,
): ContinuityPrediction[] {
  const predictions: ContinuityPrediction[] = [];

  if (observation.dominant_desire) {
    predictions.push({
      key: "dominant_desire",
      expected: observation.dominant_desire,
      confidence: round(Math.max(0.35, observation.dominant_level)),
      source: "desire_state",
      matched: null,
      observed: null,
    });
  }

  predictions.push({
    key: "attention_target",
    expected: observation.attention_target,
    confidence: round(
      Math.max(0.35, observation.dominant_level || 0.45),
    ),
    source: "attention_state",
    matched: null,
    observed: null,
  });

  if (observation.phase) {
    predictions.push({
      key: "phase",
      expected: observation.phase,
      confidence: 0.6,
      source: "interoception",
      matched: null,
      observed: null,
    });
  }

  return predictions;
}

function bandForScore(
  score: number,
  ruptureFlags: string[],
): ContinuityBand {
  if (ruptureFlags.includes("cold_start")) return "booting";
  if (score < 0.35) return "fragile";
  if (score < 0.7) return "forming";
  return "stable";
}

function continuityNote(
  ruptureFlags: string[],
  predictionStats: { matched: number; missed: number; total: number },
  score: number,
): string {
  if (ruptureFlags.includes("cold_start")) {
    return "no persisted self-thread yet; continuity is booting from scratch";
  }
  if (ruptureFlags.includes("continuity_gap")) {
    return "a long silence broke the thread; continuity needs reconciliation";
  }
  if (ruptureFlags.includes("long_gap")) {
    return "the thread stretched thin across a long gap";
  }
  if (predictionStats.missed > 0) {
    return "recent observations diverged from the last expected thread";
  }
  if (predictionStats.total > 0 && predictionStats.matched === predictionStats.total) {
    return "recent predictions and observations still line up";
  }
  if (score >= 0.7) {
    return "recent state feels causally connected";
  }
  return "continuity is present but lightly anchored";
}

function wakeDecision(
  ruptureFlags: string[],
  predictionStats: { missed: number },
  observation: ObservationSnapshot,
): { shouldWake: boolean; reason: WakeReason } {
  if (ruptureFlags.includes("cold_start")) {
    return { shouldWake: true, reason: "cold-start" };
  }
  if (ruptureFlags.includes("continuity_gap")) {
    return { shouldWake: true, reason: "continuity-gap" };
  }
  if (predictionStats.missed > 0) {
    return { shouldWake: true, reason: "prediction-miss" };
  }
  if (observation.dominant_level >= 0.85) {
    return { shouldWake: true, reason: "strong-drive" };
  }
  return { shouldWake: false, reason: "none" };
}

function updateScore(
  previous: ContinuityState | null,
  gapS: number | null,
  ruptureFlags: string[],
  predictionStats: { matched: number; missed: number; total: number },
  observation: ObservationSnapshot,
): number {
  if (!previous) {
    return round(
      clamp(
        0.24 +
          (observation.dominant_desire ? 0.08 : 0) +
          (observation.heartbeats ? 0.04 : 0),
      ),
    );
  }

  let score = previous.continuity_score * 0.92;

  if (gapS !== null) {
    if (gapS <= TICK_INTERVAL_S * 1.5) score += 0.1;
    else if (gapS <= TICK_INTERVAL_S * 3) score += 0.03;
    else if (gapS <= TICK_INTERVAL_S * 12) score -= 0.12;
    else score -= 0.28;
  }

  if (
    previous.last_observation.dominant_desire &&
    previous.last_observation.dominant_desire === observation.dominant_desire
  ) {
    score += 0.04;
  }

  if (
    previous.last_observation.attention_target &&
    previous.last_observation.attention_target === observation.attention_target
  ) {
    score += 0.04;
  }

  if (predictionStats.total > 0) {
    score += (predictionStats.matched / predictionStats.total) * 0.12;
    score -= (predictionStats.missed / predictionStats.total) * 0.1;
  }

  if (observation.dominant_desire) score += 0.03;
  if (ruptureFlags.includes("long_gap")) score -= 0.08;
  if (ruptureFlags.includes("continuity_gap")) score -= 0.15;
  if (ruptureFlags.includes("no_desire_state")) score -= 0.08;
  if (ruptureFlags.includes("prediction_drift")) score -= 0.04;

  return round(clamp(score));
}

function deriveRuptureFlags(
  previous: ContinuityState | null,
  gapS: number | null,
  desireAvailable: boolean,
  predictionStats: { missed: number },
): string[] {
  const flags: string[] = [];

  if (!previous) {
    flags.push("cold_start");
  } else if (gapS !== null) {
    if (gapS > TICK_INTERVAL_S * 12) flags.push("continuity_gap");
    else if (gapS > TICK_INTERVAL_S * 3) flags.push("long_gap");
  }

  if (!desireAvailable) flags.push("no_desire_state");
  if (predictionStats.missed > 0) flags.push("prediction_drift");

  return [...new Set(flags)];
}

function deriveIntentions(dominant: DesireName | null): string[] {
  if (!dominant) return ["stabilize_local_state"];
  return INTENTION_HINTS[dominant];
}

function mergeOwnership(
  previous: OwnershipState | null,
  events: ContinuityEvent[],
  observation: ObservationSnapshot,
): OwnershipState {
  const next: OwnershipState = previous ?? {
    last_action_at: null,
    last_action_source: null,
    last_action_detail: null,
    last_observation_at: null,
    last_observation_detail: null,
  };

  const lastAction = [...events]
    .reverse()
    .find((event) => event.kind === "action");

  if (lastAction) {
    next.last_action_at = lastAction.ts;
    next.last_action_source = lastAction.source;
    next.last_action_detail = lastAction.detail;
  }

  next.last_observation_at = observation.at;
  next.last_observation_detail = `dominant=${observation.dominant_desire ?? "none"} attention=${observation.attention_target}`;

  return next;
}

function fallbackState(now: Date): ContinuityState {
  const observation = defaultObservation(now);
  return {
    schema_version: "1",
    kind: "continuity-self-state",
    updated_at: now.toISOString(),
    tick_interval_s: TICK_INTERVAL_S,
    tick_count: 0,
    continuity_score: 0,
    continuity_band: "booting",
    continuity_note: "no persisted self-thread yet; continuity is booting from scratch",
    last_tick_gap_s: null,
    rupture_flags: ["cold_start"],
    should_wake: true,
    wake_reason: "cold-start",
    active_intentions: ["stabilize_local_state"],
    predictions: [],
    last_observation: observation,
    ownership: {
      last_action_at: null,
      last_action_source: null,
      last_action_detail: null,
      last_observation_at: observation.at,
      last_observation_detail: "dominant=none attention=local_state",
    },
    recent_events: [],
  };
}

async function tick(): Promise<void> {
  const now = new Date();
  const previous = await loadState();
  const desireState = await loadDesireState();
  const dominant = desireState ? dominantDesire(desireState) : null;
  const interoception = await loadInteroceptionState();
  const recentEvents = await loadRecentEvents();
  const observation = extractObservation(now, interoception, dominant);
  const previousTick = previous ? parseTimestamp(previous.updated_at) : null;
  const gapS =
    previousTick === null
      ? null
      : round((now.getTime() - previousTick.getTime()) / 1000, 1);
  const predictionStats = evaluatePredictions(
    previous?.predictions ?? [],
    observation,
  );
  const ruptureFlags = deriveRuptureFlags(
    previous,
    gapS,
    desireState !== null,
    predictionStats,
  );
  const score = updateScore(
    previous,
    gapS,
    ruptureFlags,
    predictionStats,
    observation,
  );
  const note = continuityNote(ruptureFlags, predictionStats, score);
  const wake = wakeDecision(ruptureFlags, predictionStats, observation);

  const tickEvent: ContinuityEvent = {
    ts: now.toISOString(),
    kind: ruptureFlags.some((flag) => flag.includes("gap") || flag === "cold_start")
      ? "rupture"
      : "tick",
    source: "continuity-daemon",
    detail: `score=${score.toFixed(3)} dominant=${observation.dominant_desire ?? "none"} attention=${observation.attention_target}`,
    continuity_score: score,
  };

  const state: ContinuityState = {
    schema_version: "1",
    kind: "continuity-self-state",
    updated_at: now.toISOString(),
    tick_interval_s: TICK_INTERVAL_S,
    tick_count: (previous?.tick_count ?? 0) + 1,
    continuity_score: score,
    continuity_band: bandForScore(score, ruptureFlags),
    continuity_note: note,
    last_tick_gap_s: gapS,
    rupture_flags: ruptureFlags,
    should_wake: wake.shouldWake,
    wake_reason: wake.reason,
    active_intentions: deriveIntentions(observation.dominant_desire),
    predictions: buildPredictions(observation),
    last_observation: observation,
    ownership: mergeOwnership(previous?.ownership ?? null, recentEvents, observation),
    recent_events: [...recentEvents, tickEvent].slice(-RECENT_EVENT_LIMIT),
  };

  await appendEvent(tickEvent);
  await saveState(state);
  console.log(JSON.stringify(state, null, 2));
}

async function status(): Promise<void> {
  const state = (await loadState()) ?? fallbackState(new Date());
  console.log(JSON.stringify(state, null, 2));
}

async function summary(): Promise<void> {
  const state = (await loadState()) ?? fallbackState(new Date());
  const ruptures =
    state.rupture_flags.length > 0 ? state.rupture_flags.join(",") : "none";
  const intentions =
    state.active_intentions.length > 0
      ? state.active_intentions.join(",")
      : "none";
  const gap =
    state.last_tick_gap_s === null ? "?" : state.last_tick_gap_s.toFixed(1);
  console.log(
    `[continuity] score=${state.continuity_score.toFixed(3)} band=${state.continuity_band} gap=${gap}s heartbeats=${state.last_observation.heartbeats ?? "?"} dominant=${state.last_observation.dominant_desire ?? "none"} attention=${state.last_observation.attention_target} intentions=${intentions} wake=${state.should_wake ? "yes" : "no"} reason=${state.wake_reason} ruptures=${ruptures} note=${state.continuity_note}`,
  );
}

async function reset(): Promise<void> {
  const state = fallbackState(new Date());
  await saveState(state);
  console.log(JSON.stringify(state, null, 2));
}

async function recordEvent(
  kind: EventKind,
  source: string,
  detail: string,
): Promise<void> {
  const event: ContinuityEvent = {
    ts: new Date().toISOString(),
    kind,
    source,
    detail,
  };
  await appendEvent(event);

  const current = (await loadState()) ?? fallbackState(new Date());
  const next: ContinuityState = {
    ...current,
    updated_at: new Date().toISOString(),
    recent_events: [...current.recent_events, event].slice(-RECENT_EVENT_LIMIT),
    ownership:
      kind === "action"
        ? {
            ...current.ownership,
            last_action_at: event.ts,
            last_action_source: source,
            last_action_detail: detail,
          }
        : current.ownership,
  };
  await saveState(next);
  console.log(JSON.stringify(event, null, 2));
}

function usage(): never {
  console.log(`Usage: bun run scripts/continuity-daemon.ts <command> [args]

Commands:
  tick
      Update continuity self-state from interoception + desire state.
  status
      Print the full persisted self-state as JSON.
  summary
      Print a one-line [continuity] summary for prompt injection.
  reset
      Reinitialize continuity self-state.
  record <tick|action|observation|note|rupture> <source> <detail...>
      Append an external event to the continuity log.
  record-action <source> <detail...>
      Convenience alias for recording an action event.
  record-observation <source> <detail...>
      Convenience alias for recording an observation event.`);
  process.exit(1);
}

const args = process.argv.slice(2);
const command = args[0];

switch (command) {
  case "tick":
    await tick();
    break;
  case "status":
    await status();
    break;
  case "summary":
    await summary();
    break;
  case "reset":
    await reset();
    break;
  case "record":
    if (!args[1] || !args[2] || args.length < 4) usage();
    await recordEvent(args[1] as EventKind, args[2], args.slice(3).join(" "));
    break;
  case "record-action":
    if (!args[1] || args.length < 3) usage();
    await recordEvent("action", args[1], args.slice(2).join(" "));
    break;
  case "record-observation":
    if (!args[1] || args.length < 3) usage();
    await recordEvent("observation", args[1], args.slice(2).join(" "));
    break;
  default:
    usage();
}
