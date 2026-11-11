import { describe, expect, it } from "vitest";
import { currentPlan } from "./plan";

describe("currentPlan", () => {
  it("returns plan_id when it is set", () => {
    expect(currentPlan({ id: "acc_1", plan_id: "plan_team" })).toBe(
      "plan_team",
    );
  });

  it("throws when the account has no plan", () => {
    expect(() => currentPlan({ id: "acc_3", plan_id: null })).toThrow(
      "has no plan",
    );
  });
});
