import { describe, expect, it } from "vitest";
import { cartTotal } from "./cart";

describe("cartTotal", () => {
  it("adds price times quantity for each item", () => {
    expect(
      cartTotal([
        { sku: "mug", price: 12, quantity: 2 },
        { sku: "tea", price: 5, quantity: 1 },
      ]),
    ).toBe(29);
  });

  it("returns zero for an empty cart", () => {
    expect(cartTotal([])).toBe(0);
  });

  it("rejects a negative quantity", () => {
    expect(() =>
      cartTotal([{ sku: "mug", price: 12, quantity: -1 }]),
    ).toThrow(RangeError);
  });

  it("rejects a fractional quantity", () => {
    expect(() =>
      cartTotal([{ sku: "mug", price: 12, quantity: 1.5 }]),
    ).toThrow(RangeError);
  });
});
