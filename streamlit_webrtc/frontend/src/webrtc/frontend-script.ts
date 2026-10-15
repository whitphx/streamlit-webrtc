export interface FrontendScriptContext {
  pc: RTCPeerConnection;
  channels: Record<string, RTCDataChannel>;
  root: HTMLDivElement;
}

export type FrontendScriptCleanup = () => void;

export type FrontendScriptSetup = (
  context: FrontendScriptContext,
) => void | FrontendScriptCleanup | Promise<void | FrontendScriptCleanup>;

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
