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

  it("retries a 502 until the receiver answers", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(null, { status: 502 }))
      .mockResolvedValueOnce(new Response(null, { status: 502 }))
      .mockResolvedValue(new Response(null));
    vi.stubGlobal("fetch", fetchMock);
    await deliver(event);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("gives up after four attempts", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 503 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(deliver(event)).rejects.toThrow("failed with 503");
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("does not retry a 4xx answer", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 410 }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(deliver(event)).rejects.toThrow("failed with 410");
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
