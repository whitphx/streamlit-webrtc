import { compileMediaConstraint } from "./media-constraint";

describe("compileMediaConstraint()", () => {
  describe("when the source object is undefined", () => {
    const src = undefined;

    it("generates an empty constraint object if no device id is provided", () => {
      expect(compileMediaConstraint(src, undefined, undefined)).toEqual({});
    });

    it("sets device IDs if provided", () => {
      expect(compileMediaConstraint(src, "videoid", "audioid")).toEqual({
        video: {
          deviceId: "videoid",
        },
        audio: {
          deviceId: "audioid",
        },
      });
    });
  });

  describe("when the source object simply contains bool specs with true value", () => {
    const src: MediaStreamConstraints = { video: true, audio: true };

    it("sets deviceIds if provided", () => {
      expect(compileMediaConstraint(src, "videoid", "audioid")).toEqual({
        video: {
          deviceId: "videoid",
        },
        audio: {
          deviceId: "audioid",
        },
      });
    });
  });

  describe("when the source object simply contains bool specs with false value", () => {
    const src: MediaStreamConstraints = { video: false, audio: false };

    it("does not set deviceIds even if provided", () => {
      expect(compileMediaConstraint(src, "videoid", "audioid")).toEqual({
        video: false,
        audio: false,
      });
    });
  });

  describe("when the source object contains complex constrants", () => {
    const src: MediaStreamConstraints = {
      video: {
        frameRate: {
          min: 10,
          max: 20,
        },
      },
      audio: {
        echoCancellation: true,
      },
    };

    it("preserves the original constrants and adds deviceIds if provided", () => {
      expect(compileMediaConstraint(src, "videoid", "audioid")).toEqual({
        video: {
          frameRate: {
            min: 10,
            max: 20,
          },
          deviceId: "videoid",
        },
        audio: {
          echoCancellation: true,
          deviceId: "audioid",
        },
      });
    });
  });
});
