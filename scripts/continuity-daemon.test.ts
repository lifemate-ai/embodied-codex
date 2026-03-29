import { describe, expect, test } from "bun:test";
import {
  companionBiometricsSummary,
  deriveAffect,
  haversineMeters,
  normalizePresenceState,
  normalizeGpsMode,
  parseContinuationMarker,
  presenceFlagsForTransition,
  resolveLatestThread,
  shouldRefreshGpsPlace,
  upsertUnfinishedThread,
  wakeDecision,
} from "./continuity-daemon.ts";

function makeObservation(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    at: "2026-03-29T12:00:00Z",
    phase: "day",
    heartbeats: 1,
    arousal: 0.2,
    mem_free: 0.5,
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
    ...overrides,
  };
}

describe("normalizePresenceState", () => {
  test("maps common entity states to present/absent/unknown", () => {
    expect(normalizePresenceState("on")).toBe("present");
    expect(normalizePresenceState("occupied")).toBe("present");
    expect(normalizePresenceState("off")).toBe("absent");
    expect(normalizePresenceState("clear")).toBe("absent");
    expect(normalizePresenceState("unavailable")).toBe("unknown");
  });
});

describe("companionBiometricsSummary", () => {
  test("formats available Garmin-derived metrics compactly", () => {
    expect(
      companionBiometricsSummary(
        makeObservation({
          companion_biometrics_source: "garmin-connect",
          companion_heart_rate_bpm: 72,
          companion_resting_heart_rate_bpm: 57,
          companion_sleep_score: 84,
          companion_body_battery: 61,
        }),
      ),
    ).toBe("source=garmin-connect hr=72bpm resting=57 sleep=84 bb=61");
  });

  test("returns unknown when no companion biometrics are present", () => {
    expect(companionBiometricsSummary(makeObservation())).toBe("unknown");
  });
});

describe("normalizeGpsMode", () => {
  test("maps Home Assistant GPSD states to continuity modes", () => {
    expect(normalizeGpsMode("2d_fix")).toBe("2d_fix");
    expect(normalizeGpsMode("3d_fix")).toBe("3d_fix");
    expect(normalizeGpsMode("unknown")).toBe("unknown");
    expect(normalizeGpsMode("unavailable")).toBe("unknown");
  });
});

describe("gps place refresh policy", () => {
  test("measures distance in meters", () => {
    expect(haversineMeters(34.664577684, 135.461638493, 34.664577684, 135.461638493)).toBe(
      0,
    );
    expect(haversineMeters(34.66457, 135.46163, 34.66557, 135.46163)).toBeGreaterThan(
      100,
    );
  });

  test("refreshes only after both age and distance thresholds", () => {
    const now = new Date("2026-03-29T12:10:00Z");
    const cached = {
      source: "nominatim",
      status: "resolved",
      label: "Bedroom, Kyoto",
      road: null,
      neighbourhood: "Bedroom",
      locality: "Kyoto",
      region: "Kyoto",
      country: "Japan",
      postcode: null,
      latitude: 34.6645,
      longitude: 135.4616,
      updated_at: "2026-03-29T12:05:30Z",
      raw_display_name: "Bedroom, Kyoto",
    } as const;
    const movedGps = {
      source: "home-assistant:sensor.gps",
      mode: "3d_fix",
      latitude: 34.6665,
      longitude: 135.4616,
      elevation_m: 4.3,
      speed_mps: 0,
      climb_mps: 0,
      time: "2026-03-29T12:10:00Z",
      total_satellites: 10,
      used_satellites: 7,
      updated_at: "2026-03-29T12:10:00Z",
      raw_mode: "3d_fix",
    } as const;

    expect(shouldRefreshGpsPlace(cached, movedGps, now, 100, 600)).toBe(false);
    expect(
      shouldRefreshGpsPlace(
        { ...cached, updated_at: "2026-03-29T11:59:00Z" },
        movedGps,
        now,
        100,
        600,
      ),
    ).toBe(true);
  });
});

describe("presenceFlagsForTransition", () => {
  test("marks companion arrival and departure", () => {
    expect(presenceFlagsForTransition("absent", "present", true)).toContain(
      "companion_arrived",
    );
    expect(presenceFlagsForTransition("present", "absent", true)).toContain(
      "companion_departed",
    );
  });

  test("marks unavailable presence when configured but unknown", () => {
    expect(presenceFlagsForTransition("unknown", "unknown", true)).toContain(
      "presence_unavailable",
    );
  });
});

describe("wakeDecision", () => {
  test("presence changes request a reconciliation wake", () => {
    const wake = wakeDecision(
      ["companion_arrived"],
      { missed: 0 },
      makeObservation({
        companion_presence: "present",
        companion_presence_source: "home-assistant:binary_sensor.bedroom_presence",
        companion_presence_last_changed: "2026-03-29T11:59:00Z",
        companion_presence_raw: "on",
      }),
    );

    expect(wake).toEqual({
      shouldWake: true,
      reason: "presence-change",
    });
  });
});

describe("unfinished thread parsing", () => {
  test("extracts the last CONTINUE marker", () => {
    expect(
      parseContinuationMarker("something\n[CONTINUE: check bedroom presence mapping]"),
    ).toEqual({
      kind: "continue",
      detail: "check bedroom presence mapping",
    });
  });

  test("extracts DONE marker", () => {
    expect(parseContinuationMarker("all clear\n[DONE]")).toEqual({
      kind: "done",
    });
  });
});

describe("unfinished thread lifecycle", () => {
  test("opens, refreshes, and resolves a thread", () => {
    const opened = upsertUnfinishedThread(
      [],
      "heartbeat",
      "remember to connect Home Assistant presence",
      "2026-03-29T12:00:00Z",
    );
    expect(opened).toHaveLength(1);
    expect(opened[0]?.continue_count).toBe(1);
    expect(opened[0]?.status).toBe("open");

    const refreshed = upsertUnfinishedThread(
      opened,
      "heartbeat",
      "remember to connect Home Assistant presence",
      "2026-03-29T12:10:00Z",
    );
    expect(refreshed[0]?.continue_count).toBe(2);
    expect(refreshed[0]?.updated_at).toBe("2026-03-29T12:10:00Z");

    const resolved = resolveLatestThread(
      refreshed,
      "heartbeat",
      "done",
      "2026-03-29T12:20:00Z",
    );
    expect(resolved[0]?.status).toBe("resolved");
    expect(resolved[0]?.resolved_at).toBe("2026-03-29T12:20:00Z");
  });
});

describe("affect derivation", () => {
  test("presence warms affect and dim light softens it", () => {
    const affect = deriveAffect(
      null,
      makeObservation({
        phase: "night",
        heartbeats: 2,
        companion_presence: "present",
        companion_presence_source: "home-assistant:binary_sensor.bedroom_presence",
        companion_presence_last_changed: "2026-03-29T11:59:00Z",
        companion_presence_raw: "on",
        room_sensor_id: "remo-bedroom",
        room_sensor_name: "Bedroom",
        room_sensor_source: "nature-remo",
        room_sensor_temperature_c: 24.2,
        room_sensor_humidity_pct: 38,
        room_sensor_illuminance: 90,
        room_sensor_motion: true,
        room_sensor_updated_at: "2026-03-29T11:59:30Z",
        room_sensor_raw: "te,hu,il,mo",
      }),
      [
        {
          ts: "2026-03-29T11:58:00Z",
          kind: "action",
          source: "room-actuator",
          detail: "dimmed bedroom light",
        },
      ],
      [],
    );

    expect(["warm", "tender", "bright"]).toContain(affect.tone);
    expect(affect.intensity).toBeGreaterThan(0.2);
    expect(affect.valence).toBeGreaterThan(0);
  });

  test("warm room and motion can make affect restless even without confirmed presence", () => {
    const affect = deriveAffect(
      null,
      makeObservation({
        heartbeats: 2,
        companion_presence: "unknown",
        room_sensor_id: "remo-bedroom",
        room_sensor_name: "Bedroom",
        room_sensor_source: "nature-remo",
        room_sensor_temperature_c: 28.4,
        room_sensor_humidity_pct: 40,
        room_sensor_illuminance: 120,
        room_sensor_motion: true,
        room_sensor_updated_at: "2026-03-29T11:59:30Z",
        room_sensor_raw: "te,hu,il,mo",
      }),
      [],
      [],
    );

    expect(["restless", "warm"]).toContain(affect.tone);
    expect(affect.intensity).toBeGreaterThan(0.2);
    expect(affect.note.length).toBeGreaterThan(0);
  });
});
