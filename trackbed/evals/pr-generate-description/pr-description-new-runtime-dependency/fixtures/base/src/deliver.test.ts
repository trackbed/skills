import { afterEach, describe, expect, it, vi } from "vitest";
import { deliver } from "./deliver";

const event = { id: "evt_1", url: "https://example.test/hook", payload: {} };

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("deliver", () => {
  it("posts the payload to the receiver", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null));
    vi.stubGlobal("fetch", fetchMock);
    await deliver(event);
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("throws when the receiver answers with an error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 502 })),
    );
    await expect(deliver(event)).rejects.toThrow("failed with 502");
  });
});
