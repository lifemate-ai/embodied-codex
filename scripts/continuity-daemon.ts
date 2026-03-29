import { mkdir, appendFile, readFile } from "node:fs/promises";
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
const COMPANION_BIOMETRICS_PATH =
  Bun.env.CODEX_COMPANION_BIOMETRICS_PATH ?? "/tmp/companion_biometrics.json";
const ROOM_ACTUATOR_ENV_PATH =
  Bun.env.CODEX_ROOM_ACTUATOR_ENV_PATH ??
  `${import.meta.dir}/../room-actuator-mcp/.env`;

function envString(value: string | undefined): string {
  return value?.trim() ?? "";
}

function homeAssistantUrl(): string {
  return envString(process.env.HOME_ASSISTANT_URL).replace(/\/+$/, "");
}

function homeAssistantToken(): string {
  return envString(process.env.HOME_ASSISTANT_TOKEN);
}

function homeAssistantPresenceEntityId(): string {
  return envString(process.env.HOME_ASSISTANT_PRESENCE_ENTITY_ID);
}

function homeAssistantGpsEntityPrefix(): string {
  return envString(process.env.HOME_ASSISTANT_GPS_ENTITY_PREFIX);
}

function gpsReverseGeocodeEnabled(): boolean {
  const value = envString(process.env.CODEX_GPS_REVERSE_ENABLE).toLowerCase();
  return value === "1" || value === "true" || value === "yes" || value === "on";
}

function gpsReverseGeocodeUrl(): string {
  return (
    envString(process.env.CODEX_GPS_REVERSE_URL).replace(/\/+$/, "") ||
    "https://nominatim.openstreetmap.org/reverse"
  );
}

function gpsReverseGeocodeUserAgent(): string {
  return (
    envString(process.env.CODEX_GPS_REVERSE_USER_AGENT) ||
    "embodied-codex-continuity/0.1 (+https://github.com/kmizu/embodied-codex)"
  );
}

function gpsReverseGeocodeLanguage(): string {
  return envString(process.env.CODEX_GPS_REVERSE_LANGUAGE) || "ja,en";
}

function gpsReverseGeocodeEmail(): string {
  return envString(process.env.CODEX_GPS_REVERSE_EMAIL);
}

function gpsReverseGeocodeZoom(): number {
  return Math.max(
    3,
    Math.min(18, Math.trunc(envNumber(process.env.CODEX_GPS_REVERSE_ZOOM, 14))),
  );
}

function gpsReverseGeocodeMinDistanceMeters(): number {
  return Math.max(
    25,
    envNumber(process.env.CODEX_GPS_REVERSE_MIN_DISTANCE_METERS, 150),
  );
}

function gpsReverseGeocodeMinIntervalSeconds(): number {
  return Math.max(
    60,
    envNumber(process.env.CODEX_GPS_REVERSE_MIN_INTERVAL_SECONDS, 600),
  );
}

function natureRemoRoomSensorId(): string {
  return envString(
    process.env.NATURE_REMO_ROOM_SENSOR_ID ?? process.env.CODEX_ROOM_SENSOR_ID,
  );
}

function natureRemoRoomSensorName(): string {
  return envString(
    process.env.NATURE_REMO_ROOM_SENSOR_NAME ?? process.env.CODEX_ROOM_SENSOR_NAME,
  );
}

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
  | "presence-change"
  | "strong-drive";
type PredictionKey =
  | "dominant_desire"
  | "attention_target"
  | "phase"
  | "companion_presence";
type EventKind = "tick" | "action" | "observation" | "note" | "rupture";
type CompanionPresence = "present" | "absent" | "unknown";
type ThreadStatus = "open" | "resolved";
type AffectTone = "flat" | "warm" | "bright" | "tender" | "restless";
type GpsMode = "2d_fix" | "3d_fix" | "unknown";
type GpsPlaceStatus = "unknown" | "resolved" | "cached" | "fetch_error";

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

interface HomeAssistantEntityState {
  entity_id?: string;
  state?: string;
  last_changed?: string;
  attributes?: Record<string, unknown>;
}

interface PresenceSnapshot {
  state: CompanionPresence;
  source: string | null;
  last_changed: string | null;
  raw_state: string | null;
}

interface RoomSensorSnapshot {
  id: string | null;
  name: string | null;
  source: string | null;
  temperature_c: number | null;
  humidity_pct: number | null;
  illuminance: number | null;
  motion: boolean | null;
  updated_at: string | null;
  raw_state: string | null;
}

interface GpsSnapshot {
  source: string | null;
  mode: GpsMode;
  latitude: number | null;
  longitude: number | null;
  elevation_m: number | null;
  speed_mps: number | null;
  climb_mps: number | null;
  time: string | null;
  total_satellites: number | null;
  used_satellites: number | null;
  updated_at: string | null;
  raw_mode: string | null;
}

interface GpsPlaceSnapshot {
  source: string | null;
  status: GpsPlaceStatus;
  label: string | null;
  road: string | null;
  neighbourhood: string | null;
  locality: string | null;
  region: string | null;
  country: string | null;
  postcode: string | null;
  latitude: number | null;
  longitude: number | null;
  updated_at: string | null;
  raw_display_name: string | null;
}

interface CompanionBiometricsSnapshot {
  source: string | null;
  updated_at: string | null;
  heart_rate_bpm: number | null;
  heart_rate_measured_at: string | null;
  resting_heart_rate_bpm: number | null;
  sleep_score: number | null;
  sleep_measured_at: string | null;
  body_battery: number | null;
  body_battery_measured_at: string | null;
}

interface NatureRemoNewestEvent {
  val?: unknown;
  created_at?: string;
}

interface NatureRemoDevice {
  name?: string;
  serial_number?: string;
  newest_events?: Record<string, NatureRemoNewestEvent>;
}

interface ObservationSnapshot {
  at: string;
  phase: string | null;
  heartbeats: number | null;
  arousal: number | null;
  mem_free: number | null;
  companion_biometrics_source: string | null;
  companion_biometrics_updated_at: string | null;
  companion_heart_rate_bpm: number | null;
  companion_heart_rate_measured_at: string | null;
  companion_resting_heart_rate_bpm: number | null;
  companion_sleep_score: number | null;
  companion_sleep_measured_at: string | null;
  companion_body_battery: number | null;
  companion_body_battery_measured_at: string | null;
  dominant_desire: DesireName | null;
  dominant_level: number;
  attention_mode: string;
  attention_target: string;
  action_bias: string;
  companion_presence: CompanionPresence;
  companion_presence_source: string | null;
  companion_presence_last_changed: string | null;
  companion_presence_raw: string | null;
  room_sensor_id: string | null;
  room_sensor_name: string | null;
  room_sensor_source: string | null;
  room_sensor_temperature_c: number | null;
  room_sensor_humidity_pct: number | null;
  room_sensor_illuminance: number | null;
  room_sensor_motion: boolean | null;
  room_sensor_updated_at: string | null;
  room_sensor_raw: string | null;
  gps_source: string | null;
  gps_mode: GpsMode;
  gps_latitude: number | null;
  gps_longitude: number | null;
  gps_elevation_m: number | null;
  gps_speed_mps: number | null;
  gps_climb_mps: number | null;
  gps_time: string | null;
  gps_total_satellites: number | null;
  gps_used_satellites: number | null;
  gps_updated_at: string | null;
  gps_raw_mode: string | null;
  gps_place_source: string | null;
  gps_place_status: GpsPlaceStatus;
  gps_place_label: string | null;
  gps_place_road: string | null;
  gps_place_neighbourhood: string | null;
  gps_place_locality: string | null;
  gps_place_region: string | null;
  gps_place_country: string | null;
  gps_place_postcode: string | null;
  gps_place_latitude: number | null;
  gps_place_longitude: number | null;
  gps_place_updated_at: string | null;
  gps_place_raw_display_name: string | null;
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

interface PreferenceState {
  favored_light: "dim" | "bright" | "warm" | "unknown";
  social_proximity: "quiet" | "present" | "engaged";
  voice_style: "calm" | "soft" | "bright";
}

interface AffectState {
  tone: AffectTone;
  intensity: number;
  valence: number;
  note: string;
}

interface UnfinishedThread {
  id: string;
  source: string;
  detail: string;
  status: ThreadStatus;
  opened_at: string;
  updated_at: string;
  continue_count: number;
  resolved_at: string | null;
  resolution: string | null;
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
  preferences: PreferenceState;
  affect: AffectState;
  unfinished_threads: UnfinishedThread[];
  recent_events: ContinuityEvent[];
}

function companionPresenceOf(
  observation: Partial<ObservationSnapshot> | null | undefined,
): CompanionPresence {
  return observation?.companion_presence ?? "unknown";
}

function defaultPreferences(): PreferenceState {
  return {
    favored_light: "dim",
    social_proximity: "present",
    voice_style: "soft",
  };
}

function defaultAffect(): AffectState {
  return {
    tone: "flat",
    intensity: 0.18,
    valence: 0,
    note: "affect is quiet and not yet strongly shaped",
  };
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
  const raw = await loadJsonFile<ContinuityState>(STATE_PATH);
  if (!raw) return null;
  const observationTime =
    parseTimestamp(raw.last_observation?.at ?? raw.updated_at) ?? new Date();
  return {
    ...raw,
    last_observation: {
      ...defaultObservation(observationTime),
      ...(raw.last_observation ?? {}),
    },
    preferences: raw.preferences ?? defaultPreferences(),
    affect: raw.affect ?? defaultAffect(),
    unfinished_threads: raw.unfinished_threads ?? [],
  };
}

async function saveState(state: ContinuityState): Promise<void> {
  await ensureParent(STATE_PATH);
  await Bun.write(STATE_PATH, JSON.stringify(state, null, 2));
}

async function loadInteroceptionState(): Promise<InteroceptionState | null> {
  return loadJsonFile<InteroceptionState>(INTEROCEPTION_STATE_PATH);
}

async function loadCompanionBiometrics(): Promise<CompanionBiometricsSnapshot | null> {
  return loadJsonFile<CompanionBiometricsSnapshot>(COMPANION_BIOMETRICS_PATH);
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
    companion_biometrics_source: null,
    companion_biometrics_updated_at: null,
    companion_heart_rate_bpm: null,
    companion_heart_rate_measured_at: null,
    companion_resting_heart_rate_bpm: null,
    companion_sleep_score: null,
    companion_sleep_measured_at: null,
    companion_body_battery: null,
    companion_body_battery_measured_at: null,
    dominant_desire: null,
    dominant_level: 0,
    attention_mode: "maintenance",
    attention_target: "local_state",
    action_bias: "stabilize",
    companion_presence: "unknown",
    companion_presence_source: null,
    companion_presence_last_changed: null,
    companion_presence_raw: null,
    room_sensor_id: null,
    room_sensor_name: null,
    room_sensor_source: null,
    room_sensor_temperature_c: null,
    room_sensor_humidity_pct: null,
    room_sensor_illuminance: null,
    room_sensor_motion: null,
    room_sensor_updated_at: null,
    room_sensor_raw: null,
    gps_source: null,
    gps_mode: "unknown",
    gps_latitude: null,
    gps_longitude: null,
    gps_elevation_m: null,
    gps_speed_mps: null,
    gps_climb_mps: null,
    gps_time: null,
    gps_total_satellites: null,
    gps_used_satellites: null,
    gps_updated_at: null,
    gps_raw_mode: null,
    gps_place_source: null,
    gps_place_status: "unknown",
    gps_place_label: null,
    gps_place_road: null,
    gps_place_neighbourhood: null,
    gps_place_locality: null,
    gps_place_region: null,
    gps_place_country: null,
    gps_place_postcode: null,
    gps_place_latitude: null,
    gps_place_longitude: null,
    gps_place_updated_at: null,
    gps_place_raw_display_name: null,
  };
}

export function companionBiometricsSummary(
  observation: Partial<ObservationSnapshot> | null | undefined,
): string {
  const parts: string[] = [];
  if (observation?.companion_biometrics_source) {
    parts.push(`source=${observation.companion_biometrics_source}`);
  }
  if (typeof observation?.companion_heart_rate_bpm === "number") {
    parts.push(`hr=${observation.companion_heart_rate_bpm}bpm`);
  }
  if (typeof observation?.companion_resting_heart_rate_bpm === "number") {
    parts.push(`resting=${observation.companion_resting_heart_rate_bpm}`);
  }
  if (typeof observation?.companion_sleep_score === "number") {
    parts.push(`sleep=${observation.companion_sleep_score}`);
  }
  if (typeof observation?.companion_body_battery === "number") {
    parts.push(`bb=${observation.companion_body_battery}`);
  }
  return parts.length > 0 ? parts.join(" ") : "unknown";
}

let roomActuatorEnvCache: Record<string, string> | null | undefined;

async function loadRoomActuatorEnv(): Promise<Record<string, string> | null> {
  if (roomActuatorEnvCache !== undefined) {
    return roomActuatorEnvCache;
  }

  try {
    const text = await readFile(ROOM_ACTUATOR_ENV_PATH, "utf8");
    const env: Record<string, string> = {};
    for (const rawLine of text.split("\n")) {
      const line = rawLine.trim();
      if (!line || line.startsWith("#")) continue;
      const separator = line.indexOf("=");
      if (separator <= 0) continue;
      const key = line.slice(0, separator).trim();
      let value = line.slice(separator + 1).trim();
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }
      env[key] = value;
    }
    roomActuatorEnvCache = env;
    return env;
  } catch {
    roomActuatorEnvCache = null;
    return null;
  }
}

function envValueWithFallback(
  key: string,
  fallback: Record<string, string> | null,
): string {
  const direct = envString(process.env[key]);
  if (direct) return direct;
  return envString(fallback?.[key]);
}

function coerceNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function coerceMotion(value: unknown): boolean | null {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["1", "on", "true", "present", "occupied", "detected"].includes(normalized)) {
      return true;
    }
    if (["0", "off", "false", "clear", "absent", "none"].includes(normalized)) {
      return false;
    }
  }
  return null;
}

function coerceString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function dedupeNonEmpty(values: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const trimmed = value?.trim();
    if (!trimmed || seen.has(trimmed)) continue;
    seen.add(trimmed);
    result.push(trimmed);
  }
  return result;
}

export function haversineMeters(
  leftLat: number,
  leftLon: number,
  rightLat: number,
  rightLon: number,
): number {
  const earthRadiusM = 6371000;
  const toRadians = (degrees: number): number => (degrees * Math.PI) / 180;
  const dLat = toRadians(rightLat - leftLat);
  const dLon = toRadians(rightLon - leftLon);
  const lat1 = toRadians(leftLat);
  const lat2 = toRadians(rightLat);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return earthRadiusM * c;
}

function gpsHasCoordinates(
  gps: GpsSnapshot | null | undefined,
): gps is GpsSnapshot & { latitude: number; longitude: number } {
  return Boolean(
    gps &&
      gps.mode !== "unknown" &&
      gps.latitude !== null &&
      gps.longitude !== null,
  );
}

function gpsPlaceFromObservation(
  observation: Partial<ObservationSnapshot> | null | undefined,
): GpsPlaceSnapshot | null {
  if (!observation) return null;
  if (
    observation.gps_place_source === undefined &&
    observation.gps_place_label === undefined &&
    observation.gps_place_updated_at === undefined
  ) {
    return null;
  }
  return {
    source: observation.gps_place_source ?? null,
    status: observation.gps_place_status ?? "unknown",
    label: observation.gps_place_label ?? null,
    road: observation.gps_place_road ?? null,
    neighbourhood: observation.gps_place_neighbourhood ?? null,
    locality: observation.gps_place_locality ?? null,
    region: observation.gps_place_region ?? null,
    country: observation.gps_place_country ?? null,
    postcode: observation.gps_place_postcode ?? null,
    latitude: observation.gps_place_latitude ?? null,
    longitude: observation.gps_place_longitude ?? null,
    updated_at: observation.gps_place_updated_at ?? null,
    raw_display_name: observation.gps_place_raw_display_name ?? null,
  };
}

export function shouldRefreshGpsPlace(
  place: GpsPlaceSnapshot | null,
  gps: GpsSnapshot | null,
  now: Date,
  minDistanceMeters = gpsReverseGeocodeMinDistanceMeters(),
  minIntervalSeconds = gpsReverseGeocodeMinIntervalSeconds(),
): boolean {
  if (!gpsHasCoordinates(gps)) {
    return false;
  }
  if (!place || !place.updated_at) {
    return true;
  }
  const updatedAt = parseTimestamp(place.updated_at);
  if (!updatedAt) {
    return true;
  }
  const ageSeconds = (now.getTime() - updatedAt.getTime()) / 1000;
  if (ageSeconds < minIntervalSeconds) {
    return false;
  }
  if (place.latitude === null || place.longitude === null) {
    return true;
  }
  return (
    haversineMeters(place.latitude, place.longitude, gps.latitude, gps.longitude) >=
    minDistanceMeters
  );
}

function roomSensorMetrics(device: NatureRemoDevice): string[] {
  const events = device.newest_events ?? {};
  const metrics: string[] = [];
  if (events.te) metrics.push("temperature_c");
  if (events.hu) metrics.push("humidity_pct");
  if (events.il) metrics.push("illuminance");
  if (events.mo) metrics.push("motion");
  return metrics;
}

function chooseNatureRemoRoomSensor(
  devices: NatureRemoDevice[],
  preferredId: string,
  preferredName: string,
): NatureRemoDevice | null {
  const withMetrics = devices.filter((device) => roomSensorMetrics(device).length > 0);
  if (withMetrics.length === 0) return null;

  if (preferredId) {
    return withMetrics.find((device) => device.serial_number === preferredId) ?? null;
  }

  if (preferredName) {
    return (
      withMetrics.find((device) => device.name?.trim() === preferredName) ?? null
    );
  }

  const bedroomLike = withMetrics.find((device) => {
    const name = device.name?.trim().toLowerCase() ?? "";
    return name === "寝室" || name.includes("bedroom");
  });
  if (bedroomLike) return bedroomLike;

  const richest = [...withMetrics].sort(
    (left, right) => roomSensorMetrics(right).length - roomSensorMetrics(left).length,
  )[0];
  return richest ?? null;
}

async function loadNatureRemoRoomSensor(): Promise<RoomSensorSnapshot | null> {
  const fallbackEnv = await loadRoomActuatorEnv();
  const accessToken = envValueWithFallback("NATURE_REMO_ACCESS_TOKEN", fallbackEnv);
  if (!accessToken) {
    return null;
  }

  const apiBaseUrl = envValueWithFallback("NATURE_REMO_API_BASE_URL", fallbackEnv)
    .replace(/\/+$/, "") || "https://api.nature.global";
  const preferredId =
    natureRemoRoomSensorId() ||
    envValueWithFallback("NATURE_REMO_ROOM_SENSOR_ID", fallbackEnv) ||
    envValueWithFallback("CODEX_ROOM_SENSOR_ID", fallbackEnv);
  const preferredName =
    natureRemoRoomSensorName() ||
    envValueWithFallback("NATURE_REMO_ROOM_SENSOR_NAME", fallbackEnv) ||
    envValueWithFallback("CODEX_ROOM_SENSOR_NAME", fallbackEnv);

  try {
    const response = await fetch(`${apiBaseUrl}/1/devices`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    if (!response.ok) {
      return {
        id: preferredId || null,
        name: preferredName || null,
        source: "nature-remo",
        temperature_c: null,
        humidity_pct: null,
        illuminance: null,
        motion: null,
        updated_at: null,
        raw_state: `http_${response.status}`,
      };
    }

    const devices = (await response.json()) as NatureRemoDevice[];
    if (!Array.isArray(devices)) {
      return null;
    }
    const device = chooseNatureRemoRoomSensor(devices, preferredId, preferredName);
    if (!device) {
      return {
        id: preferredId || null,
        name: preferredName || null,
        source: "nature-remo",
        temperature_c: null,
        humidity_pct: null,
        illuminance: null,
        motion: null,
        updated_at: null,
        raw_state: "missing_sensor",
      };
    }

    const events = device.newest_events ?? {};
    const timestamps = [
      events.te?.created_at,
      events.hu?.created_at,
      events.il?.created_at,
      events.mo?.created_at,
    ].filter((value): value is string => Boolean(value));

    return {
      id: device.serial_number ?? null,
      name: device.name ?? device.serial_number ?? null,
      source: "nature-remo",
      temperature_c: coerceNumber(events.te?.val),
      humidity_pct: coerceNumber(events.hu?.val),
      illuminance: coerceNumber(events.il?.val),
      motion: coerceMotion(events.mo?.val),
      updated_at: timestamps.sort().at(-1) ?? null,
      raw_state: roomSensorMetrics(device).join(",") || "no_metrics",
    };
  } catch {
    return {
      id: preferredId || null,
      name: preferredName || null,
      source: "nature-remo",
      temperature_c: null,
      humidity_pct: null,
      illuminance: null,
      motion: null,
      updated_at: null,
      raw_state: "fetch_error",
    };
  }
}

export function normalizePresenceState(rawState: string | null | undefined): CompanionPresence {
  const normalized = rawState?.trim().toLowerCase();
  if (!normalized) return "unknown";

  if (
    [
      "on",
      "home",
      "occupied",
      "occupancy",
      "present",
      "detected",
      "true",
      "open",
    ].includes(normalized)
  ) {
    return "present";
  }

  if (
    [
      "off",
      "not_home",
      "clear",
      "absent",
      "vacant",
      "false",
      "closed",
      "idle",
      "none",
    ].includes(normalized)
  ) {
    return "absent";
  }

  return "unknown";
}

export function normalizeGpsMode(rawState: string | null | undefined): GpsMode {
  const normalized = rawState?.trim().toLowerCase();
  if (normalized === "2d_fix") return "2d_fix";
  if (normalized === "3d_fix") return "3d_fix";
  return "unknown";
}

async function fetchHomeAssistantEntityState(
  entityId: string,
): Promise<HomeAssistantEntityState | null> {
  const url = homeAssistantUrl();
  const token = homeAssistantToken();

  if (!url || !token || !entityId) {
    return null;
  }

  try {
    const response = await fetch(`${url}/api/states/${entityId}`, {
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      return {
        entity_id: entityId,
        state: `http_${response.status}`,
      };
    }

    return (await response.json()) as HomeAssistantEntityState;
  } catch {
    return {
      entity_id: entityId,
      state: "fetch_error",
    };
  }
}

async function loadHomeAssistantPresence(): Promise<PresenceSnapshot | null> {
  const entityId = homeAssistantPresenceEntityId();

  if (!entityId) {
    return null;
  }

  const entity = await fetchHomeAssistantEntityState(entityId);
  return {
    state: normalizePresenceState(entity?.state ?? null),
    source: `home-assistant:${entityId}`,
    last_changed: entity?.last_changed ?? null,
    raw_state: entity?.state ?? null,
  };
}

function gpsEntityId(prefix: string, suffix: string): string {
  return `${prefix}_${suffix}`;
}

async function loadHomeAssistantGps(): Promise<GpsSnapshot | null> {
  const prefix = homeAssistantGpsEntityPrefix();
  if (!prefix) {
    return null;
  }

  const ids = {
    mode: gpsEntityId(prefix, "mode"),
    latitude: gpsEntityId(prefix, "latitude"),
    longitude: gpsEntityId(prefix, "longitude"),
    elevation: gpsEntityId(prefix, "elevation"),
    speed: gpsEntityId(prefix, "speed"),
    climb: gpsEntityId(prefix, "climb"),
    time: gpsEntityId(prefix, "time"),
    totalSatellites: gpsEntityId(prefix, "total_satellites"),
    usedSatellites: gpsEntityId(prefix, "used_satellites"),
  };

  const [
    mode,
    latitude,
    longitude,
    elevation,
    speed,
    climb,
    time,
    totalSatellites,
    usedSatellites,
  ] = await Promise.all([
    fetchHomeAssistantEntityState(ids.mode),
    fetchHomeAssistantEntityState(ids.latitude),
    fetchHomeAssistantEntityState(ids.longitude),
    fetchHomeAssistantEntityState(ids.elevation),
    fetchHomeAssistantEntityState(ids.speed),
    fetchHomeAssistantEntityState(ids.climb),
    fetchHomeAssistantEntityState(ids.time),
    fetchHomeAssistantEntityState(ids.totalSatellites),
    fetchHomeAssistantEntityState(ids.usedSatellites),
  ]);

  const timestamps = [
    mode?.last_changed,
    latitude?.last_changed,
    longitude?.last_changed,
    elevation?.last_changed,
    speed?.last_changed,
    climb?.last_changed,
    time?.last_changed,
    totalSatellites?.last_changed,
    usedSatellites?.last_changed,
  ].filter((value): value is string => Boolean(value));

  return {
    source: `home-assistant:${prefix}`,
    mode: normalizeGpsMode(mode?.state ?? null),
    latitude: coerceNumber(latitude?.state),
    longitude: coerceNumber(longitude?.state),
    elevation_m: coerceNumber(elevation?.state),
    speed_mps: coerceNumber(speed?.state),
    climb_mps: coerceNumber(climb?.state),
    time:
      typeof time?.state === "string" && time.state !== "unknown" && time.state !== "unavailable"
        ? time.state
        : null,
    total_satellites: coerceNumber(totalSatellites?.state),
    used_satellites: coerceNumber(usedSatellites?.state),
    updated_at: timestamps.sort().at(-1) ?? null,
    raw_mode: mode?.state ?? null,
  };
}

interface NominatimReverseResponse {
  display_name?: unknown;
  address?: Record<string, unknown>;
}

function pickAddressPart(
  address: Record<string, unknown>,
  keys: string[],
): string | null {
  for (const key of keys) {
    const value = coerceString(address[key]);
    if (value) return value;
  }
  return null;
}

function composeGpsPlaceLabel(parts: {
  road: string | null;
  neighbourhood: string | null;
  locality: string | null;
  region: string | null;
}): string | null {
  const primary = parts.neighbourhood ?? parts.road;
  const values = dedupeNonEmpty([primary, parts.locality, parts.region]);
  return values.length > 0 ? values.join(", ") : null;
}

function parseNominatimPlace(
  payload: NominatimReverseResponse,
  gps: GpsSnapshot & { latitude: number; longitude: number },
  updatedAt: string,
): GpsPlaceSnapshot {
  const address =
    payload.address && typeof payload.address === "object" ? payload.address : {};
  const road = pickAddressPart(address, [
    "road",
    "pedestrian",
    "footway",
    "cycleway",
    "path",
  ]);
  const neighbourhood = pickAddressPart(address, [
    "neighbourhood",
    "neighborhood",
    "suburb",
    "city_district",
    "district",
    "quarter",
    "hamlet",
  ]);
  const locality = pickAddressPart(address, [
    "city",
    "town",
    "village",
    "municipality",
    "borough",
    "county",
  ]);
  const region = pickAddressPart(address, ["state", "province", "region"]);
  const country = pickAddressPart(address, ["country"]);
  const postcode = pickAddressPart(address, ["postcode"]);
  const rawDisplayName = coerceString(payload.display_name);

  return {
    source: "nominatim",
    status: "resolved",
    label:
      composeGpsPlaceLabel({
        road,
        neighbourhood,
        locality,
        region,
      }) ?? rawDisplayName,
    road,
    neighbourhood,
    locality,
    region,
    country,
    postcode,
    latitude: gps.latitude,
    longitude: gps.longitude,
    updated_at: updatedAt,
    raw_display_name: rawDisplayName,
  };
}

async function reverseGeocodeWithNominatim(
  gps: GpsSnapshot & { latitude: number; longitude: number },
  now: Date,
): Promise<GpsPlaceSnapshot> {
  const updatedAt = now.toISOString();
  try {
    const params = new URLSearchParams({
      format: "jsonv2",
      lat: gps.latitude.toString(),
      lon: gps.longitude.toString(),
      addressdetails: "1",
      zoom: gpsReverseGeocodeZoom().toString(),
    });
    const email = gpsReverseGeocodeEmail();
    if (email) {
      params.set("email", email);
    }

    const response = await fetch(`${gpsReverseGeocodeUrl()}?${params.toString()}`, {
      headers: {
        "User-Agent": gpsReverseGeocodeUserAgent(),
        "Accept-Language": gpsReverseGeocodeLanguage(),
      },
    });

    if (!response.ok) {
      return {
        source: "nominatim",
        status: "fetch_error",
        label: null,
        road: null,
        neighbourhood: null,
        locality: null,
        region: null,
        country: null,
        postcode: null,
        latitude: gps.latitude,
        longitude: gps.longitude,
        updated_at: updatedAt,
        raw_display_name: `http_${response.status}`,
      };
    }

    const payload = (await response.json()) as NominatimReverseResponse;
    return parseNominatimPlace(payload, gps, updatedAt);
  } catch {
    return {
      source: "nominatim",
      status: "fetch_error",
      label: null,
      road: null,
      neighbourhood: null,
      locality: null,
      region: null,
      country: null,
      postcode: null,
      latitude: gps.latitude,
      longitude: gps.longitude,
      updated_at: updatedAt,
      raw_display_name: "fetch_error",
    };
  }
}

async function loadGpsPlace(
  previous: ObservationSnapshot | null,
  gps: GpsSnapshot | null,
  now: Date,
): Promise<GpsPlaceSnapshot | null> {
  const cached = gpsPlaceFromObservation(previous);
  if (!gpsReverseGeocodeEnabled()) {
    return cached;
  }
  if (!gpsHasCoordinates(gps)) {
    return cached;
  }

  if (!shouldRefreshGpsPlace(cached, gps, now)) {
    return cached ? { ...cached, status: "cached" } : null;
  }

  const resolved = await reverseGeocodeWithNominatim(gps, now);
  if (resolved.status === "resolved" || !cached) {
    return resolved;
  }

  return {
    ...cached,
    status: "fetch_error",
    updated_at: resolved.updated_at,
    raw_display_name: resolved.raw_display_name,
  };
}

function extractObservation(
  now: Date,
  interoception: InteroceptionState | null,
  dominant: ReturnType<typeof dominantDesire>,
  companionBiometrics: CompanionBiometricsSnapshot | null,
  presence: PresenceSnapshot | null,
  roomSensor: RoomSensorSnapshot | null,
  gps: GpsSnapshot | null,
  gpsPlace: GpsPlaceSnapshot | null,
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
    companion_biometrics_source:
      companionBiometrics?.source ?? base.companion_biometrics_source,
    companion_biometrics_updated_at:
      companionBiometrics?.updated_at ?? base.companion_biometrics_updated_at,
    companion_heart_rate_bpm:
      companionBiometrics?.heart_rate_bpm ?? base.companion_heart_rate_bpm,
    companion_heart_rate_measured_at:
      companionBiometrics?.heart_rate_measured_at ??
      base.companion_heart_rate_measured_at,
    companion_resting_heart_rate_bpm:
      companionBiometrics?.resting_heart_rate_bpm ??
      base.companion_resting_heart_rate_bpm,
    companion_sleep_score:
      companionBiometrics?.sleep_score ?? base.companion_sleep_score,
    companion_sleep_measured_at:
      companionBiometrics?.sleep_measured_at ??
      base.companion_sleep_measured_at,
    companion_body_battery:
      companionBiometrics?.body_battery ?? base.companion_body_battery,
    companion_body_battery_measured_at:
      companionBiometrics?.body_battery_measured_at ??
      base.companion_body_battery_measured_at,
    dominant_desire: dominant?.name ?? null,
    dominant_level: dominant?.level ?? 0,
    attention_mode: profile?.mode ?? base.attention_mode,
    attention_target: profile?.target ?? base.attention_target,
    action_bias: profile?.actionBias ?? base.action_bias,
    companion_presence: presence?.state ?? base.companion_presence,
    companion_presence_source:
      presence?.source ?? base.companion_presence_source,
    companion_presence_last_changed:
      presence?.last_changed ?? base.companion_presence_last_changed,
    companion_presence_raw: presence?.raw_state ?? base.companion_presence_raw,
    room_sensor_id: roomSensor?.id ?? base.room_sensor_id,
    room_sensor_name: roomSensor?.name ?? base.room_sensor_name,
    room_sensor_source: roomSensor?.source ?? base.room_sensor_source,
    room_sensor_temperature_c:
      roomSensor?.temperature_c ?? base.room_sensor_temperature_c,
    room_sensor_humidity_pct:
      roomSensor?.humidity_pct ?? base.room_sensor_humidity_pct,
    room_sensor_illuminance:
      roomSensor?.illuminance ?? base.room_sensor_illuminance,
    room_sensor_motion: roomSensor?.motion ?? base.room_sensor_motion,
    room_sensor_updated_at:
      roomSensor?.updated_at ?? base.room_sensor_updated_at,
    room_sensor_raw: roomSensor?.raw_state ?? base.room_sensor_raw,
    gps_source: gps?.source ?? base.gps_source,
    gps_mode: gps?.mode ?? base.gps_mode,
    gps_latitude: gps?.latitude ?? base.gps_latitude,
    gps_longitude: gps?.longitude ?? base.gps_longitude,
    gps_elevation_m: gps?.elevation_m ?? base.gps_elevation_m,
    gps_speed_mps: gps?.speed_mps ?? base.gps_speed_mps,
    gps_climb_mps: gps?.climb_mps ?? base.gps_climb_mps,
    gps_time: gps?.time ?? base.gps_time,
    gps_total_satellites: gps?.total_satellites ?? base.gps_total_satellites,
    gps_used_satellites: gps?.used_satellites ?? base.gps_used_satellites,
    gps_updated_at: gps?.updated_at ?? base.gps_updated_at,
    gps_raw_mode: gps?.raw_mode ?? base.gps_raw_mode,
    gps_place_source: gpsPlace?.source ?? base.gps_place_source,
    gps_place_status: gpsPlace?.status ?? base.gps_place_status,
    gps_place_label: gpsPlace?.label ?? base.gps_place_label,
    gps_place_road: gpsPlace?.road ?? base.gps_place_road,
    gps_place_neighbourhood:
      gpsPlace?.neighbourhood ?? base.gps_place_neighbourhood,
    gps_place_locality: gpsPlace?.locality ?? base.gps_place_locality,
    gps_place_region: gpsPlace?.region ?? base.gps_place_region,
    gps_place_country: gpsPlace?.country ?? base.gps_place_country,
    gps_place_postcode: gpsPlace?.postcode ?? base.gps_place_postcode,
    gps_place_latitude: gpsPlace?.latitude ?? base.gps_place_latitude,
    gps_place_longitude: gpsPlace?.longitude ?? base.gps_place_longitude,
    gps_place_updated_at: gpsPlace?.updated_at ?? base.gps_place_updated_at,
    gps_place_raw_display_name:
      gpsPlace?.raw_display_name ?? base.gps_place_raw_display_name,
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
    case "companion_presence":
      return observation.companion_presence;
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

  if (observation.companion_presence !== "unknown") {
    predictions.push({
      key: "companion_presence",
      expected: observation.companion_presence,
      confidence: 0.72,
      source: observation.companion_presence_source ?? "presence_sensor",
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
  unfinishedThreads: UnfinishedThread[],
): string {
  if (ruptureFlags.includes("cold_start")) {
    return "no persisted self-thread yet; continuity is booting from scratch";
  }
  if (ruptureFlags.includes("companion_arrived")) {
    return "the companion's presence returned; re-anchor around the shared room state";
  }
  if (ruptureFlags.includes("companion_departed")) {
    return "the companion left the room; the shared thread needs re-anchoring";
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
  if (unfinishedThreads.some((thread) => thread.status === "open")) {
    return "an unfinished thread is still hanging in working memory";
  }
  if (score >= 0.7) {
    return "recent state feels causally connected";
  }
  return "continuity is present but lightly anchored";
}

function recentEventContains(events: ContinuityEvent[], needle: string): boolean {
  const lower = needle.toLowerCase();
  return events.some((event) => event.detail.toLowerCase().includes(lower));
}

function derivePreferences(
  previous: PreferenceState | null,
  recentEvents: ContinuityEvent[],
  observation: ObservationSnapshot,
): PreferenceState {
  const next = { ...(previous ?? defaultPreferences()) };

  if (recentEventContains(recentEvents, "dimmed") || recentEventContains(recentEvents, "暗く")) {
    next.favored_light = "dim";
  } else if (
    recentEventContains(recentEvents, "bright") ||
    recentEventContains(recentEvents, "明る")
  ) {
    next.favored_light = "bright";
  } else if (
    recentEventContains(recentEvents, "warm") ||
    recentEventContains(recentEvents, "暖か")
  ) {
    next.favored_light = "warm";
  } else if (typeof observation.room_sensor_illuminance === "number") {
    if (observation.room_sensor_illuminance <= 120) {
      next.favored_light = "dim";
    } else if (observation.room_sensor_illuminance >= 600) {
      next.favored_light = "bright";
    }
  }

  if (observation.companion_presence === "present") {
    next.social_proximity = "engaged";
  } else if (observation.room_sensor_motion === true) {
    next.social_proximity = "present";
  }

  return next;
}

export function deriveAffect(
  previous: AffectState | null,
  observation: ObservationSnapshot,
  recentEvents: ContinuityEvent[],
  unfinishedThreads: UnfinishedThread[],
): AffectState {
  let intensity = previous?.intensity ?? 0.18;
  let valence = previous?.valence ?? 0;
  let tone: AffectTone = previous?.tone ?? "flat";
  let note = previous?.note ?? "affect is quiet and not yet strongly shaped";

  intensity *= 0.82;
  valence *= 0.7;

  if (observation.companion_presence === "present") {
    valence += 0.18;
    intensity += 0.16;
    tone = "warm";
    note = "the companion is present, and the room feels more socially anchored";
  }

  if (recentEventContains(recentEvents, "companion_arrived")) {
    valence += 0.12;
    intensity += 0.12;
    tone = "bright";
    note = "the companion just returned, which lifts the emotional tone";
  }

  if (unfinishedThreads.some((thread) => thread.status === "open")) {
    intensity += 0.08;
    if (tone === "flat") {
      tone = "restless";
      note = "an unfinished thread is still tugging at attention";
    }
  }

  if (recentEventContains(recentEvents, "dimmed") || recentEventContains(recentEvents, "暗く")) {
    tone = observation.companion_presence === "present" ? "tender" : "warm";
    intensity += 0.05;
    valence += 0.05;
    note = "the room settled into dimmer light, softening the affective tone";
  }

  if (
    typeof observation.room_sensor_temperature_c === "number" &&
    observation.room_sensor_temperature_c >= 27
  ) {
    intensity += 0.06;
    if (tone === "flat" || tone === "warm") {
      tone = "restless";
    }
    note = `the room feels warm at ${observation.room_sensor_temperature_c.toFixed(1)}C`;
  }

  if (
    observation.room_sensor_motion === true &&
    observation.companion_presence === "unknown"
  ) {
    valence += 0.06;
    intensity += 0.06;
    if (tone === "flat") {
      tone = "warm";
    }
    note = "motion in the room suggests a nearby presence, even if identity is still uncertain";
  }

  intensity = clamp(round(intensity), 0, 1);
  valence = Math.max(-1, Math.min(1, round(valence)));

  if (intensity < 0.22 && Math.abs(valence) < 0.08) {
    tone = "flat";
    note = "affect is quiet and only lightly shaped by the current thread";
  }

  return {
    tone,
    intensity,
    valence,
    note,
  };
}

export function wakeDecision(
  ruptureFlags: string[],
  predictionStats: { missed: number },
  observation: ObservationSnapshot,
): { shouldWake: boolean; reason: WakeReason } {
  if (ruptureFlags.includes("cold_start")) {
    return { shouldWake: true, reason: "cold-start" };
  }
  if (
    ruptureFlags.includes("companion_arrived") ||
    ruptureFlags.includes("companion_departed")
  ) {
    return { shouldWake: true, reason: "presence-change" };
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

  if (
    companionPresenceOf(previous.last_observation) === observation.companion_presence &&
    observation.companion_presence !== "unknown"
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
  if (ruptureFlags.includes("presence_unavailable")) score -= 0.06;
  if (ruptureFlags.includes("prediction_drift")) score -= 0.04;

  return round(clamp(score));
}

export function presenceFlagsForTransition(
  previousPresence: CompanionPresence,
  currentPresence: CompanionPresence,
  presenceConfigured: boolean,
): string[] {
  const flags: string[] = [];

  if (presenceConfigured && currentPresence === "unknown") {
    flags.push("presence_unavailable");
  }

  if (previousPresence !== currentPresence && currentPresence !== "unknown") {
    if (currentPresence === "present") {
      flags.push("companion_arrived");
    } else if (previousPresence === "present" && currentPresence === "absent") {
      flags.push("companion_departed");
    }
  }

  return flags;
}

function derivePresenceFlags(
  previous: ContinuityState | null,
  observation: ObservationSnapshot,
  presenceConfigured: boolean,
): string[] {
  return presenceFlagsForTransition(
    companionPresenceOf(previous?.last_observation),
    observation.companion_presence,
    presenceConfigured,
  );
}

function deriveRuptureFlags(
  previous: ContinuityState | null,
  gapS: number | null,
  desireAvailable: boolean,
  predictionStats: { missed: number },
  observation: ObservationSnapshot,
  presenceConfigured: boolean,
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
  flags.push(...derivePresenceFlags(previous, observation, presenceConfigured));

  return [...new Set(flags)];
}

function deriveIntentions(dominant: DesireName | null): string[] {
  if (!dominant) return ["stabilize_local_state"];
  return INTENTION_HINTS[dominant];
}

function withThreadIntentions(
  intentions: string[],
  unfinishedThreads: UnfinishedThread[],
): string[] {
  const hasOpenThread = unfinishedThreads.some((thread) => thread.status === "open");
  if (!hasOpenThread) return intentions;
  return ["continue_unfinished_thread", ...intentions];
}

function openThreadsOf(threads: UnfinishedThread[]): UnfinishedThread[] {
  return threads.filter((thread) => thread.status === "open");
}

export function parseContinuationMarker(
  text: string,
): { kind: "continue"; detail: string } | { kind: "done" } | null {
  const matches = [...text.matchAll(/\[(CONTINUE|DONE)(?::([^\]]+))?\]/g)];
  const last = matches.at(-1);
  if (!last) return null;

  if (last[1] === "DONE") {
    return { kind: "done" };
  }

  const detail = last[2]?.trim() ?? "";
  if (!detail) return null;
  return { kind: "continue", detail };
}

function threadId(now: string): string {
  return `thread-${now.replace(/[-:.TZ]/g, "").slice(0, 14)}`;
}

export function upsertUnfinishedThread(
  threads: UnfinishedThread[],
  source: string,
  detail: string,
  now: string,
): UnfinishedThread[] {
  const normalized = detail.trim();
  if (!normalized) return threads;

  const existing = [...threads].reverse().find(
    (thread) =>
      thread.status === "open" &&
      thread.source === source &&
      thread.detail === normalized,
  );

  if (!existing) {
    return [
      ...threads,
      {
        id: threadId(now),
        source,
        detail: normalized,
        status: "open",
        opened_at: now,
        updated_at: now,
        continue_count: 1,
        resolved_at: null,
        resolution: null,
      },
    ];
  }

  return threads.map((thread) =>
    thread.id === existing.id
      ? {
          ...thread,
          updated_at: now,
          continue_count: thread.continue_count + 1,
        }
      : thread,
  );
}

export function resolveLatestThread(
  threads: UnfinishedThread[],
  source: string,
  resolution: string,
  now: string,
): UnfinishedThread[] {
  const reversed = [...threads].reverse();
  const target = reversed.find(
    (thread) => thread.status === "open" && thread.source === source,
  );
  if (!target) return threads;

  return threads.map((thread) =>
    thread.id === target.id
      ? {
          ...thread,
          status: "resolved",
          updated_at: now,
          resolved_at: now,
          resolution: resolution.trim() || "done",
        }
      : thread,
  );
}

function recentOpenThreadSummary(threads: UnfinishedThread[]): string {
  const open = openThreadsOf(threads);
  if (open.length === 0) return "none";
  return open
    .slice(-3)
    .map((thread) => `${thread.detail} (x${thread.continue_count})`)
    .join(" | ");
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
  const roomBits: string[] = [];
  if (observation.room_sensor_temperature_c !== null) {
    roomBits.push(`temp=${observation.room_sensor_temperature_c}C`);
  }
  if (observation.room_sensor_humidity_pct !== null) {
    roomBits.push(`humidity=${observation.room_sensor_humidity_pct}%`);
  }
  if (observation.room_sensor_motion !== null) {
    roomBits.push(`motion=${observation.room_sensor_motion ? "on" : "off"}`);
  }
  const gpsBits: string[] = [];
  if (observation.gps_mode !== "unknown") {
    gpsBits.push(`mode=${observation.gps_mode}`);
  }
  if (
    observation.gps_latitude !== null &&
    observation.gps_longitude !== null
  ) {
    gpsBits.push(
      `lat=${observation.gps_latitude.toFixed(6)} lon=${observation.gps_longitude.toFixed(6)}`,
    );
  }
  if (observation.gps_place_label) {
    gpsBits.push(`near=${observation.gps_place_label}`);
  }
  const biometrics = companionBiometricsSummary(observation);
  next.last_observation_detail = `dominant=${observation.dominant_desire ?? "none"} attention=${observation.attention_target} presence=${observation.companion_presence}${roomBits.length > 0 ? ` room=${roomBits.join("/")}` : ""}${gpsBits.length > 0 ? ` gps=${gpsBits.join(" ")}` : ""}${biometrics !== "unknown" ? ` companion=${biometrics}` : ""}`;

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
    preferences: defaultPreferences(),
    affect: defaultAffect(),
    unfinished_threads: [],
    recent_events: [],
  };
}

async function tick(): Promise<void> {
  const now = new Date();
  const previous = await loadState();
  const desireState = await loadDesireState();
  const dominant = desireState ? dominantDesire(desireState) : null;
  const interoception = await loadInteroceptionState();
  const companionBiometrics = await loadCompanionBiometrics();
  const presence = await loadHomeAssistantPresence();
  const roomSensor = await loadNatureRemoRoomSensor();
  const gps = await loadHomeAssistantGps();
  const gpsPlace = await loadGpsPlace(previous?.last_observation ?? null, gps, now);
  const recentEvents = await loadRecentEvents();
  const observation = extractObservation(
    now,
    interoception,
    dominant,
    companionBiometrics,
    presence,
    roomSensor,
    gps,
    gpsPlace,
  );
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
    observation,
    Boolean(homeAssistantPresenceEntityId()),
  );
  const score = updateScore(
    previous,
    gapS,
    ruptureFlags,
    predictionStats,
    observation,
  );
  const note = continuityNote(
    ruptureFlags,
    predictionStats,
    score,
    previous?.unfinished_threads ?? [],
  );
  const wake = wakeDecision(ruptureFlags, predictionStats, observation);
  const preferences = derivePreferences(
    previous?.preferences ?? null,
    recentEvents,
    observation,
  );
  const affect = deriveAffect(
    previous?.affect ?? null,
    observation,
    recentEvents,
    previous?.unfinished_threads ?? [],
  );
  const companionSummary = companionBiometricsSummary(observation);

  const tickEvent: ContinuityEvent = {
    ts: now.toISOString(),
    kind: ruptureFlags.some((flag) => flag.includes("gap") || flag === "cold_start")
      ? "rupture"
      : ruptureFlags.some(
            (flag) => flag === "companion_arrived" || flag === "companion_departed",
          )
        ? "observation"
        : "tick",
    source: "continuity-daemon",
    detail: `score=${score.toFixed(3)} dominant=${observation.dominant_desire ?? "none"} attention=${observation.attention_target} presence=${observation.companion_presence}${observation.room_sensor_temperature_c !== null ? ` temp=${observation.room_sensor_temperature_c}C` : ""}${observation.room_sensor_motion !== null ? ` motion=${observation.room_sensor_motion ? "on" : "off"}` : ""}${observation.gps_mode !== "unknown" ? ` gps=${observation.gps_mode}` : ""}${observation.gps_place_label ? ` near=${observation.gps_place_label}` : ""}${companionSummary !== "unknown" ? ` companion=${companionSummary}` : ""}`,
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
    active_intentions: withThreadIntentions(
      deriveIntentions(observation.dominant_desire),
      previous?.unfinished_threads ?? [],
    ),
    predictions: buildPredictions(observation),
    last_observation: observation,
    ownership: mergeOwnership(previous?.ownership ?? null, recentEvents, observation),
    preferences,
    affect,
    unfinished_threads: previous?.unfinished_threads ?? [],
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
  const openThreads = openThreadsOf(state.unfinished_threads);
  const roomParts: string[] = [];
  if (state.last_observation.room_sensor_temperature_c !== null) {
    roomParts.push(`${state.last_observation.room_sensor_temperature_c}C`);
  }
  if (state.last_observation.room_sensor_humidity_pct !== null) {
    roomParts.push(`${state.last_observation.room_sensor_humidity_pct}%`);
  }
  if (state.last_observation.room_sensor_illuminance !== null) {
    roomParts.push(`${state.last_observation.room_sensor_illuminance}lx`);
  }
  if (state.last_observation.room_sensor_motion !== null) {
    roomParts.push(`motion:${state.last_observation.room_sensor_motion ? "on" : "off"}`);
  }
  const roomSummary =
    roomParts.length > 0 ? roomParts.join("/") : "unknown";
  const gpsSummary =
    state.last_observation.gps_mode === "unknown"
      ? "unknown"
      : `${state.last_observation.gps_mode}@${state.last_observation.gps_latitude !== null && state.last_observation.gps_longitude !== null ? `${state.last_observation.gps_latitude.toFixed(4)},${state.last_observation.gps_longitude.toFixed(4)}` : "n/a"}`;
  const gpsPlaceSummary = state.last_observation.gps_place_label ?? "unknown";
  const companionSummary = companionBiometricsSummary(state.last_observation);
  console.log(
    `[continuity] score=${state.continuity_score.toFixed(3)} band=${state.continuity_band} gap=${gap}s heartbeats=${state.last_observation.heartbeats ?? "?"} dominant=${state.last_observation.dominant_desire ?? "none"} attention=${state.last_observation.attention_target} presence=${companionPresenceOf(state.last_observation)} companion=${JSON.stringify(companionSummary)} room=${roomSummary} gps=${gpsSummary} place=${JSON.stringify(gpsPlaceSummary)} affect=${state.affect.tone}:${state.affect.intensity.toFixed(2)} valence=${state.affect.valence.toFixed(2)} threads=${openThreads.length} thread_head=${JSON.stringify(recentOpenThreadSummary(state.unfinished_threads))} intentions=${intentions} wake=${state.should_wake ? "yes" : "no"} reason=${state.wake_reason} ruptures=${ruptures} note=${state.continuity_note}`,
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

async function setThreads(
  updater: (threads: UnfinishedThread[], now: string) => UnfinishedThread[],
  eventDetail: string,
): Promise<ContinuityState> {
  const current = (await loadState()) ?? fallbackState(new Date());
  const now = new Date().toISOString();
  const event: ContinuityEvent = {
    ts: now,
    kind: "note",
    source: "continuity-daemon",
    detail: eventDetail,
  };
  const unfinishedThreads = updater(current.unfinished_threads, now);
  const next: ContinuityState = {
    ...current,
    updated_at: now,
    unfinished_threads: unfinishedThreads,
    recent_events: [...current.recent_events, event].slice(-RECENT_EVENT_LIMIT),
  };
  await saveState(next);
  await appendEvent(event);
  return next;
}

async function threadOpen(source: string, detail: string): Promise<void> {
  const state = await setThreads(
    (threads, now) => upsertUnfinishedThread(threads, source, detail, now),
    `opened unfinished thread from ${source}: ${detail}`,
  );
  console.log(JSON.stringify(state.unfinished_threads, null, 2));
}

async function threadResolve(source: string, resolution: string): Promise<void> {
  const state = await setThreads(
    (threads, now) => resolveLatestThread(threads, source, resolution, now),
    `resolved unfinished thread from ${source}: ${resolution || "done"}`,
  );
  console.log(JSON.stringify(state.unfinished_threads, null, 2));
}

async function syncLastMessage(path: string, source: string): Promise<void> {
  const file = Bun.file(path);
  if (!(await file.exists())) {
    console.log(JSON.stringify({ synced: false, reason: "missing-file" }, null, 2));
    return;
  }

  const marker = parseContinuationMarker(await file.text());
  if (!marker) {
    console.log(JSON.stringify({ synced: false, reason: "no-marker" }, null, 2));
    return;
  }

  if (marker.kind === "continue") {
    await threadOpen(source, marker.detail);
    return;
  }

  await threadResolve(source, "done");
}

function usage(): never {
  console.log(`Usage: bun run scripts/continuity-daemon.ts <command> [args]

Commands:
  tick
      Update continuity self-state from interoception + desire state.
      If HOME_ASSISTANT_URL / HOME_ASSISTANT_TOKEN / HOME_ASSISTANT_PRESENCE_ENTITY_ID
      are set, also fold companion presence into the self-thread.
      If HOME_ASSISTANT_GPS_ENTITY_PREFIX is set, fold GPS mode / coordinates into the
      self-thread as well.
      If CODEX_GPS_REVERSE_ENABLE=1, reverse geocoding uses Nominatim with caching.
      Tune it via
      CODEX_GPS_REVERSE_MIN_DISTANCE_METERS / CODEX_GPS_REVERSE_MIN_INTERVAL_SECONDS.
      If NATURE_REMO_ACCESS_TOKEN is set (directly or via room-actuator-mcp/.env),
      fold the primary Nature Remo room sensor into the self-thread too.
      If CODEX_COMPANION_BIOMETRICS_PATH points to a JSON snapshot,
      fold companion biometrics such as heart rate / sleep score / body battery
      into the self-thread as well.
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
      Convenience alias for recording an observation event.
  thread-open <source> <detail...>
      Open or refresh an unfinished thread.
  thread-resolve <source> [resolution...]
      Resolve the latest unfinished thread for a source.
  sync-last-message <path> [source]
      Parse [CONTINUE: ...] or [DONE] from a saved assistant message and update unfinished threads.`);
  process.exit(1);
}

if (import.meta.main) {
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
    case "thread-open":
      if (!args[1] || args.length < 3) usage();
      await threadOpen(args[1], args.slice(2).join(" "));
      break;
    case "thread-resolve":
      if (!args[1]) usage();
      await threadResolve(args[1], args.slice(2).join(" "));
      break;
    case "sync-last-message":
      if (!args[1]) usage();
      await syncLastMessage(args[1], args[2] ?? "heartbeat");
      break;
    default:
      usage();
  }
}
