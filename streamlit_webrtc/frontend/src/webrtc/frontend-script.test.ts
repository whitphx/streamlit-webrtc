import { describe, expect, it, vi } from "vitest";
import { loadFrontendScript, setUpFrontendScript } from "./frontend-script";

describe("loadFrontendScript", () => {
  it("returns the module's default export", async () => {
    const setup = await loadFrontendScript(
      "export default function setup(ctx) { return ctx.channels.events + '%#/?'; }",
    );

    expect(
      setup({
        channels: { events: "ok" },
      } as unknown as Parameters<typeof setup>[0]),
    ).toBe("ok%#/?");
  });

  it("rejects a module without a default function", async () => {
    await expect(loadFrontendScript("export const x = 1;")).rejects.toThrow(
      "frontend_script must `export default` a function",
    );
  });
});

describe("setUpFrontendScript", () => {
  const context = {} as Parameters<typeof setUpFrontendScript>[1];

  it("takes a returned function as the cleanup", async () => {
    const cleanup = vi.fn();

    const handle = await setUpFrontendScript(() => cleanup, context);
    handle.cleanup?.();

    expect(cleanup).toHaveBeenCalledOnce();
    expect(handle.update).toBeUndefined();
  });

  it("calls a returned object's update and cleanup as its methods", async () => {
    class Overlay {
      calls: unknown[] = [];
      update(data: unknown) {
        this.calls.push(data);
      }
      cleanup() {
        this.calls.push("cleanup");
      }
    }
    const overlay = new Overlay();

    const handle = await setUpFrontendScript(async () => overlay, context);
    handle.update?.({ color: "red" });
    handle.cleanup?.();

    expect(overlay.calls).toEqual([{ color: "red" }, "cleanup"]);
  });

  it("accepts a script that returns nothing", async () => {
    expect(await setUpFrontendScript(() => {}, context)).toEqual({});
  });
});
