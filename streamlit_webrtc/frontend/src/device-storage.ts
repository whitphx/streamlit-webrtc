// Persists the user's input-device selection across page reloads.
//
// Two scopes are written on every selection:
//   - per-component, keyed by the Streamlit component's `key` argument
//   - global, shared across every webrtc_streamer instance on this origin
//
// On load we prefer the per-component entry and fall back to the global one,
// so a first-time component instance picks up the user's last choice while
// already-configured instances keep their own.

const GLOBAL_KEY = "streamlit-webrtc:device-ids";
const PER_COMPONENT_PREFIX = "streamlit-webrtc:device-ids:";

export interface PersistedDeviceIds {
  video?: MediaDeviceInfo["deviceId"];
  audio?: MediaDeviceInfo["deviceId"];
}

function safeLocalStorage(): Storage | null {
  try {
    return typeof window !== "undefined" ? window.localStorage : null;
  } catch {
    // localStorage access can throw in sandboxed iframes or when site data
    // is blocked.
    return null;
  }
}

function read(key: string): PersistedDeviceIds | null {
  const storage = safeLocalStorage();
  if (storage == null) return null;
  let raw: string | null;
  try {
    raw = storage.getItem(key);
  } catch {
    return null;
  }
  if (raw == null) return null;
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (parsed == null || typeof parsed !== "object") return null;
    const { video, audio } = parsed as Record<string, unknown>;
    const result: PersistedDeviceIds = {};
    if (typeof video === "string") result.video = video;
    if (typeof audio === "string") result.audio = audio;
    return result;
  } catch {
    return null;
  }
}

function write(key: string, value: PersistedDeviceIds): void {
  const storage = safeLocalStorage();
  if (storage == null) return;
  try {
    storage.setItem(key, JSON.stringify(value));
  } catch {
    // QuotaExceededError, SecurityError, etc. — persistence is best-effort.
  }
}

export function loadPersistedDeviceIds(
  componentKey: string | undefined,
): PersistedDeviceIds {
  if (componentKey != null) {
    const perComponent = read(PER_COMPONENT_PREFIX + componentKey);
    if (perComponent != null) return perComponent;
  }
  return read(GLOBAL_KEY) ?? {};
}

export function persistDeviceIds(
  componentKey: string | undefined,
  deviceIds: PersistedDeviceIds,
): void {
  // Skip writing an entry with no usable IDs to avoid clobbering an existing
  // selection with `{}` during the brief window before devices are opened.
  if (deviceIds.video == null && deviceIds.audio == null) return;
  write(GLOBAL_KEY, deviceIds);
  if (componentKey != null) {
    write(PER_COMPONENT_PREFIX + componentKey, deviceIds);
  }
}
