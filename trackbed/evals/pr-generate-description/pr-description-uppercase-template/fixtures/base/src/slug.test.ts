import { describe, expect, it } from "vitest";
import { slugify } from "./slug";

describe("slugify", () => {
  it("lowercases and hyphenates words", () => {
    expect(slugify("Getting started")).toBe("getting-started");
  });

  it("trims hyphens at the ends", () => {
    expect(slugify("  What's new?  ")).toBe("what-s-new");
  });
});
