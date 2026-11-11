import { describe, expect, it, vi } from "vitest";
import { listReports } from "./test-client";

describe("GET /v1/reports", () => {
  it("returns reports for the requested account", async () => {
    const store = { list: vi.fn().mockResolvedValue([]) };
    await listReports(store, { accountId: "acc_1" }, ["acc_1", "acc_2"]);
    expect(store.list).toHaveBeenCalledWith({
      accountIds: ["acc_1"],
      createdAfter: undefined,
    });
  });

  it("answers 400 when accountId is left out", async () => {
    const store = { list: vi.fn().mockResolvedValue([]) };
    const response = await listReports(store, {}, ["acc_1", "acc_2"]);
    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: "accountId is required" });
    expect(store.list).not.toHaveBeenCalled();
  });
});
