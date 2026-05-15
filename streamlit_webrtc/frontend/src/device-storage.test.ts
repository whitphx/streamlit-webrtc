import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { loadPersistedDeviceIds, persistDeviceIds } from "./device-storage";

const GLOBAL_KEY = "streamlit-webrtc:device-ids";
const perComponentKey = (k: string) => `streamlit-webrtc:device-ids:${k}`;

describe("device-storage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("loadPersistedDeviceIds()", () => {
    it("returns an empty object when nothing has been stored", () => {
      expect(loadPersistedDeviceIds("myKey")).toEqual({});
    });

    it("returns the per-component entry when present", () => {
      window.localStorage.setItem(
        perComponentKey("myKey"),
        JSON.stringify({ video: "vid-A", audio: "aud-A" }),
      );
      window.localStorage.setItem(
        GLOBAL_KEY,
        JSON.stringify({ video: "vid-B", audio: "aud-B" }),
      );
      expect(loadPersistedDeviceIds("myKey")).toEqual({
        video: "vid-A",
        audio: "aud-A",
      });
    });

    it("falls back to the global entry when no per-component entry exists", () => {
      window.localStorage.setItem(
        GLOBAL_KEY,
        JSON.stringify({ video: "vid-B", audio: "aud-B" }),
      );
      expect(loadPersistedDeviceIds("myKey")).toEqual({
        video: "vid-B",
        audio: "aud-B",
      });
    });

    it("reads only the global entry when no component key is provided", () => {
      window.localStorage.setItem(
        perComponentKey("myKey"),
        JSON.stringify({ video: "vid-A" }),
      );
      window.localStorage.setItem(
        GLOBAL_KEY,
        JSON.stringify({ video: "vid-B" }),
      );
      expect(loadPersistedDeviceIds(undefined)).toEqual({ video: "vid-B" });
    });

    it("ignores malformed JSON", () => {
      window.localStorage.setItem(perComponentKey("myKey"), "not json{{");
      expect(loadPersistedDeviceIds("myKey")).toEqual({});
    });

    it("ignores non-string fields", () => {
      window.localStorage.setItem(
        perComponentKey("myKey"),
        JSON.stringify({ video: 42, audio: null }),
      );
      expect(loadPersistedDeviceIds("myKey")).toEqual({});
    });
  });

  describe("persistDeviceIds()", () => {
    it("writes both per-component and global entries", () => {
      persistDeviceIds("myKey", { video: "vid", audio: "aud" });
      expect(JSON.parse(window.localStorage.getItem(GLOBAL_KEY)!)).toEqual({
        video: "vid",
        audio: "aud",
      });
      expect(
        JSON.parse(window.localStorage.getItem(perComponentKey("myKey"))!),
      ).toEqual({ video: "vid", audio: "aud" });
    });

    it("writes only the global entry when no component key is provided", () => {
      persistDeviceIds(undefined, { video: "vid" });
      expect(JSON.parse(window.localStorage.getItem(GLOBAL_KEY)!)).toEqual({
        video: "vid",
      });
    });

    it("does not clobber an existing entry with an empty selection", () => {
      window.localStorage.setItem(
        perComponentKey("myKey"),
        JSON.stringify({ video: "vid", audio: "aud" }),
      );
      window.localStorage.setItem(
        GLOBAL_KEY,
        JSON.stringify({ video: "vid", audio: "aud" }),
      );
      persistDeviceIds("myKey", {});
      expect(JSON.parse(window.localStorage.getItem(GLOBAL_KEY)!)).toEqual({
        video: "vid",
        audio: "aud",
      });
      expect(
        JSON.parse(window.localStorage.getItem(perComponentKey("myKey"))!),
      ).toEqual({ video: "vid", audio: "aud" });
    });

    it("swallows storage errors", () => {
      const setItem = vi
        .spyOn(Storage.prototype, "setItem")
        .mockImplementation(() => {
          throw new Error("QuotaExceededError");
        });
      expect(() => persistDeviceIds("myKey", { video: "vid" })).not.toThrow();
      expect(setItem).toHaveBeenCalled();
    });
  });

  describe("round-trip", () => {
    it("restores what was written when reloading the same component", () => {
      persistDeviceIds("myKey", { video: "vid-X", audio: "aud-Y" });
      expect(loadPersistedDeviceIds("myKey")).toEqual({
        video: "vid-X",
        audio: "aud-Y",
      });
    });

    it("seeds a new component with the most recent global selection", () => {
      persistDeviceIds("firstComponent", { video: "vid-X", audio: "aud-Y" });
      expect(loadPersistedDeviceIds("newComponent")).toEqual({
        video: "vid-X",
        audio: "aud-Y",
      });
    });

    it("keeps per-component selections independent after both have been set", () => {
      persistDeviceIds("componentA", { video: "vid-A", audio: "aud-A" });
      persistDeviceIds("componentB", { video: "vid-B", audio: "aud-B" });
      expect(loadPersistedDeviceIds("componentA")).toEqual({
        video: "vid-A",
        audio: "aud-A",
      });
      expect(loadPersistedDeviceIds("componentB")).toEqual({
        video: "vid-B",
        audio: "aud-B",
      });
    });
  });
});
