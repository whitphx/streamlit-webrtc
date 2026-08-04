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

function remove(key: string): void {
  const storage = safeLocalStorage();
  if (storage == null) return;
  try {
    storage.removeItem(key);
  } catch {
    // SecurityError, etc. — persistence is best-effort.
  }
}

export function persistDeviceIds(
  componentKey: string | undefined,
  deviceIds: PersistedDeviceIds,
  { clearing }: { clearing: boolean } = { clearing: false },
): void {
  const keys = [GLOBAL_KEY];
  if (componentKey != null) {
    keys.push(PER_COMPONENT_PREFIX + componentKey);
  }

  if (deviceIds.video == null && deviceIds.audio == null) {
    // An empty selection is normally the brief window before devices are
    // opened, and writing it would clobber a stored choice that is still good.
    // `clearing` marks the other case, where the IDs were dropped because
    // their devices no longer exist.
    if (!clearing) return;
    // Removed rather than stored as an empty entry, which would count as a
    // per-component selection and cut this component off from the global
    // fallback for good.
    keys.forEach(remove);
    return;
  }

  keys.forEach((key) => write(key, deviceIds));
}
