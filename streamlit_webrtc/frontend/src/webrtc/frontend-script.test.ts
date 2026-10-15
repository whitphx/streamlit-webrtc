import { describe, expect, it } from "vitest";
import { loadFrontendScript } from "./frontend-script";

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
