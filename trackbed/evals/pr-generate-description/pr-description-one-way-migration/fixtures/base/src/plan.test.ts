import { describe, expect, it } from "vitest";
import { currentPlan } from "./plan";

describe("currentPlan", () => {
  it("returns plan_id when it is set", () => {
    expect(
      currentPlan({ id: "acc_1", plan_id: "plan_team", legacy_plan: "plus" }),
    ).toBe("plan_team");
  });

  it("falls back to the legacy plan name", () => {
    expect(
      currentPlan({ id: "acc_2", plan_id: null, legacy_plan: "max" }),
    ).toBe("plan_business");
  });

  it("throws when the account has no plan", () => {
    expect(() =>
      currentPlan({ id: "acc_3", plan_id: null, legacy_plan: null }),
    ).toThrow("has no plan");
  });
});
