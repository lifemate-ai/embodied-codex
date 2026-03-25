/**
 * Attention state — derives a compact attention-control summary from current desire state.
 *
 * This is intentionally not a sentiment label. It describes where attention is likely
 * to be pulled under the current continuous-control regime.
 */

const SCRIPT_DIR = import.meta.dir;
const HOME_DIR = Bun.env.HOME ?? "";
const CANDIDATE_PATHS = [
  Bun.env.CODEX_DESIRES_PATH,
  Bun.env.DESIRES_PATH,
  `${SCRIPT_DIR}/../desires.json`,
  HOME_DIR ? `${HOME_DIR}/.codex/desires.json` : "",
].filter(Boolean);

type DesireName =
  | "look_outside"
  | "browse_curiosity"
  | "miss_companion"
  | "observe_room";

interface DesirePayload {
  updated_at?: string;
  dominant?: string;
  desires?: Record<string, number>;
}

interface AttentionProfile {
  mode: string;
  target: string;
  scope: string;
  actionBias: string;
  summary: string;
}

const ATTENTION_MAP: Record<DesireName, AttentionProfile> = {
  look_outside: {
    mode: "outward-orienting",
    target: "window_sky_outside",
    scope: "far",
    actionBias: "reorient_and_observe",
    summary: "attention wants to turn outward and check the sky or the outside world.",
  },
  browse_curiosity: {
    mode: "epistemic-exploration",
    target: "novel_information",
    scope: "wide",
    actionBias: "search_and_learn",
    summary: "attention is pulled toward unanswered questions and novel information.",
  },
  miss_companion: {
    mode: "social-reconnection",
    target: "companion_presence_voice",
    scope: "person",
    actionBias: "seek_social_cues",
    summary: "attention wants to check for the companion's presence or voice.",
  },
  observe_room: {
    mode: "environmental-monitoring",
    target: "room_changes_local_anomalies",
    scope: "near",
    actionBias: "scan_for_drift",
    summary: "attention is drawn to local room changes, drift, and small anomalies.",
  },
};

async function loadDesireState(): Promise<DesirePayload | null> {
  for (const path of CANDIDATE_PATHS) {
    const file = Bun.file(path);
    if (!(await file.exists())) continue;
    try {
      return (await file.json()) as DesirePayload;
    } catch {
      // Try next candidate.
    }
  }
  return null;
}

function dominantDesire(
  payload: DesirePayload,
): { name: DesireName; level: number } | null {
  const desires = payload.desires ?? {};
  const candidates = Object.entries(desires)
    .filter(([name, level]) => name in ATTENTION_MAP && typeof level === "number")
    .map(([name, level]) => ({ name: name as DesireName, level }));

  if (candidates.length === 0) return null;

  if (payload.dominant && payload.dominant in ATTENTION_MAP) {
    const level = desires[payload.dominant] ?? 0;
    return { name: payload.dominant as DesireName, level };
  }

  return candidates.reduce((best, current) =>
    current.level > best.level ? current : best,
  );
}

function urgencyBand(level: number): string {
  if (level >= 0.8) return "high";
  if (level >= 0.5) return "medium";
  return "low";
}

function stability(level: number): string {
  if (level >= 0.7) return "locked";
  if (level >= 0.35) return "forming";
  return "diffuse";
}

function fallbackAttention(): string {
  return "[attention] mode=maintenance target=local_state scope=near action_bias=stabilize urgency=low stability=diffuse note=attention is currently broad and lightly anchored.";
}

const payload = await loadDesireState();
if (!payload) {
  console.log(fallbackAttention());
  process.exit(0);
}

const dominant = dominantDesire(payload);
if (!dominant) {
  console.log(fallbackAttention());
  process.exit(0);
}

const profile = ATTENTION_MAP[dominant.name];
const urgency = urgencyBand(dominant.level);
const lock = stability(dominant.level);

console.log(
  `[attention] mode=${profile.mode} target=${profile.target} scope=${profile.scope} action_bias=${profile.actionBias} urgency=${urgency} stability=${lock} dominant=${dominant.name} level=${dominant.level.toFixed(3)} note=${profile.summary}`,
);
