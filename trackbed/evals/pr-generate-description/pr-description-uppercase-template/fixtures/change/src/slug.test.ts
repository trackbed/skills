import { describe, expect, it } from "vitest";
import { slugify } from "./slug";

describe("slugify", () => {
  it("lowercases and hyphenates words", () => {
    expect(slugify("Getting started")).toBe("getting-started");
  });

  it("trims hyphens at the ends", () => {
    expect(slugify("  What's new?  ")).toBe("what-s-new");
  });

  it("keeps the base letter of an accented letter", () => {
    expect(slugify("Crème brûlée")).toBe("creme-brulee");
    expect(slugify("Ångström")).toBe("angstrom");
  });

  it("still hyphenates letters that have no base letter", () => {
    expect(slugify("Smørrebrød")).toBe("sm-rrebr-d");
  });
});
