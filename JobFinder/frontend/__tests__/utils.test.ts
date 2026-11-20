import { cn } from "@/lib/utils";

describe("cn", () => {
  it("merges class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("filters falsy values", () => {
    expect(cn("foo", false, undefined, null, "bar")).toBe("foo bar");
  });

  it("returns empty string for no arguments", () => {
    expect(cn()).toBe("");
  });

  it("deduplicates conflicting tailwind classes via tailwind-merge", () => {
    // tailwind-merge keeps the last conflicting utility class
    expect(cn("px-2", "px-4")).toBe("px-4");
    expect(cn("text-sm", "text-lg")).toBe("text-lg");
  });

  it("preserves non-conflicting classes", () => {
    expect(cn("flex", "items-center", "gap-2")).toBe("flex items-center gap-2");
  });

  it("handles conditional objects", () => {
    expect(cn("base", { active: true, hidden: false })).toBe("base active");
  });
});
