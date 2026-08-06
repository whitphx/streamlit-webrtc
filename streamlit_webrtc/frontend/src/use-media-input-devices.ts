import { useCallback, useEffect, useRef, useState } from "react";

export interface MediaInputDevices {
  video: MediaDeviceInfo[];
  audio: MediaDeviceInfo[];
}

const NO_DEVICES: MediaInputDevices = { video: [], audio: [] };

// Ref: https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/ondevicechange#example
export function useMediaInputDevices() {
  const [devices, setDevices] = useState<MediaInputDevices>(NO_DEVICES);

  const unavailable =
    typeof navigator?.mediaDevices?.enumerateDevices !== "function";

  // Device labels stay empty until the user grants media permission, so a
  // caller holding the permission prompt refreshes once it is granted. That
  // result must survive an earlier enumeration resolving late.
  const latestRequestIdRef = useRef(0);
  const refresh = useCallback(async (): Promise<void> => {
    if (typeof navigator?.mediaDevices?.enumerateDevices !== "function") {
      return;
    }
    const requestId = ++latestRequestIdRef.current;
    const allDevices = await navigator.mediaDevices.enumerateDevices();
    if (latestRequestIdRef.current !== requestId) {
      return;
    }
    // Before permission is granted browsers report one placeholder entry per
    // kind, carrying no ID and no label. Those name no device that can be
    // opened, selected or remembered, so they are not devices as far as
    // callers are concerned.
    const devices = allDevices.filter((device) => device.deviceId !== "");
    setDevices({
      video: devices.filter((device) => device.kind === "videoinput"),
      audio: devices.filter((device) => device.kind === "audioinput"),
    });
  }, []);

  useEffect(() => {
    const enumerate = () => {
      // Nothing awaits these two, unlike the caller-driven `refresh()`, so a
      // failure would otherwise disappear.
      refresh().catch((error) =>
        console.error("Failed to enumerate media devices", error),
      );
    };

    enumerate();

    // `addEventListener` rather than the `ondevicechange` property so several
    // components can watch the device list at once.
    navigator?.mediaDevices?.addEventListener("devicechange", enumerate);
    return () => {
      navigator?.mediaDevices?.removeEventListener("devicechange", enumerate);
    };
  }, [refresh]);

  return { devices, unavailable, refresh };
}
