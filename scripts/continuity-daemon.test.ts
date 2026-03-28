import { describe, expect, test } from "bun:test";
import {
  deriveAffect,
  normalizePresenceState,
  parseContinuationMarker,
  resolveLatestThread,
  presenceFlagsForTransition,
  upsertUnfinishedThread,
  wakeDecision,
} from "./continuity-daemon.ts";

describe("normalizePresenceState", () => {
  test("maps common entity states to present/absent/unknown", () => {
    expect(normalizePresenceState("on")).toBe("present");
    expect(normalizePresenceState("occupied")).toBe("present");
    expect(normalizePresenceState("off")).toBe("absent");
    expect(normalizePresenceState("clear")).toBe("absent");
    expect(normalizePresenceState("unavailable")).toBe("unknown");
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
      {
        at: "2026-03-29T12:00:00Z",
        phase: "day",
        heartbeats: 1,
        arousal: 0.2,
        mem_free: 0.5,
        dominant_desire: null,
        dominant_level: 0,
        attention_mode: "maintenance",
        attention_target: "local_state",
        action_bias: "stabilize",
        companion_presence: "present",
        companion_presence_source: "home-assistant:binary_sensor.bedroom_presence",
        companion_presence_last_changed: "2026-03-29T11:59:00Z",
        companion_presence_raw: "on",
      },
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
      {
        at: "2026-03-29T12:00:00Z",
        phase: "night",
        heartbeats: 2,
        arousal: 0.2,
        mem_free: 0.5,
        dominant_desire: null,
        dominant_level: 0,
        attention_mode: "maintenance",
        attention_target: "local_state",
        action_bias: "stabilize",
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
      },
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
      {
        at: "2026-03-29T12:00:00Z",
        phase: "day",
        heartbeats: 2,
        arousal: 0.2,
        mem_free: 0.5,
        dominant_desire: null,
        dominant_level: 0,
        attention_mode: "maintenance",
        attention_target: "local_state",
        action_bias: "stabilize",
        companion_presence: "unknown",
        companion_presence_source: null,
        companion_presence_last_changed: null,
        companion_presence_raw: null,
        room_sensor_id: "remo-bedroom",
        room_sensor_name: "Bedroom",
        room_sensor_source: "nature-remo",
        room_sensor_temperature_c: 28.4,
        room_sensor_humidity_pct: 40,
        room_sensor_illuminance: 120,
        room_sensor_motion: true,
        room_sensor_updated_at: "2026-03-29T11:59:30Z",
        room_sensor_raw: "te,hu,il,mo",
      },
      [],
      [],
    );

    expect(["restless", "warm"]).toContain(affect.tone);
    expect(affect.intensity).toBeGreaterThan(0.2);
    expect(affect.note.length).toBeGreaterThan(0);
  });
});
