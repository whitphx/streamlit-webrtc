import { compileMediaConstraints, getMediaUsage } from "./media-constraint";

describe("compileMediaConstraints()", () => {
  describe("when the source object is undefined", () => {
    const src = undefined;

    it("generates an empty constraint object if no device id is provided", () => {
      expect(compileMediaConstraints(src, undefined, undefined)).toEqual({});
    });

    it("sets device IDs if provided", () => {
      expect(compileMediaConstraints(src, "videoid", "audioid")).toEqual({
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
      expect(compileMediaConstraints(src, "videoid", "audioid")).toEqual({
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
      expect(compileMediaConstraints(src, "videoid", "audioid")).toEqual({
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
      expect(compileMediaConstraints(src, "videoid", "audioid")).toEqual({
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

describe("getMediaUsage()", () => {
  describe("when the input is undefined", () => {
    const constraintsFromPython = undefined;

    it("returns true for both video and audio", () => {
      expect(getMediaUsage(constraintsFromPython)).toEqual({
        videoEnabled: true,
        audioEnabled: true,
      });
    });
  });

  describe("when the input contains true values", () => {
    const constraintsFromPython: MediaStreamConstraints = {
      video: true,
      audio: true,
    };

    it("reflects the input constrants", () => {
      expect(getMediaUsage(constraintsFromPython)).toEqual({
        videoEnabled: true,
        audioEnabled: true,
      });
    });
  });

  describe("when the input contains false values", () => {
    const constraintsFromPython: MediaStreamConstraints = {
      video: false,
      audio: false,
    };

    it("reflects the input constrants", () => {
      expect(getMediaUsage(constraintsFromPython)).toEqual({
        videoEnabled: false,
        audioEnabled: false,
      });
    });
  });

  describe("when the input contains complex objects", () => {
    const constraintsFromPython: MediaStreamConstraints = {
      video: {
        frameRate: { min: 10, max: 15 },
      },
      audio: { echoCancellation: true },
    };

    it("reflects the input constrants", () => {
      expect(getMediaUsage(constraintsFromPython)).toEqual({
        videoEnabled: true,
        audioEnabled: true,
      });
    });
  });
});
