export interface FrontendScriptMedia {
  video?: HTMLVideoElement;
  audio?: HTMLAudioElement;
}

export interface FrontendScriptContext {
  pc: RTCPeerConnection;
  channels: Record<string, RTCDataChannel>;
  root: HTMLDivElement;
  media: FrontendScriptMedia;
  data: unknown;
}

export interface FrontendScriptHandle {
  update?: (data: unknown) => void;
  cleanup?: () => void;
}

export type FrontendScriptSetup = (
  context: FrontendScriptContext,
) =>
  | void
  | (() => void)
  | FrontendScriptHandle
  | Promise<void | (() => void) | FrontendScriptHandle>;

export class FrontendScriptError extends Error {
  name = "FrontendScriptError";
  constructor(error: unknown) {
    super(error instanceof Error ? error.message : String(error));
  }
}

export async function loadFrontendScript(
  source: string,
): Promise<FrontendScriptSetup> {
  // A data: URL rather than a blob: URL, because Node (and so the unit
  // tests) can import the former but not the latter.
  const url = `data:text/javascript;charset=utf-8,${encodeURIComponent(source)}`;
  const module = await import(/* @vite-ignore */ url);
  if (typeof module.default !== "function") {
    throw new Error("frontend_script must `export default` a function");
  }
  return module.default;
}

export async function setUpFrontendScript(
  setup: FrontendScriptSetup,
  context: FrontendScriptContext,
): Promise<FrontendScriptHandle> {
  const result = await setup(context);
  if (typeof result === "function") {
    return { cleanup: result };
  }
  if (result == null) {
    return {};
  }
  // Called as methods so that a script returning a class instance
  // keeps its `this`.
  return {
    update:
      typeof result.update === "function"
        ? (data) => result.update?.(data)
        : undefined,
    cleanup:
      typeof result.cleanup === "function"
        ? () => result.cleanup?.()
        : undefined,
  };
}
