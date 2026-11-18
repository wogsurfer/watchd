import { describe, expect, it } from "vitest";
import { layoutWeeks, weeksUntil } from "./calendar";

describe("calendar weeks", () => {
  it("always shows the first weeks, even empty", () => {
    expect(layoutWeeks([0, 0, 1, 0, 0], 5)).toEqual([0, 1, 2, 3, 4].map((index) => ({ type: "week", index })));
  });

  it("after them shows only busy weeks, with empty runs as one gap", () => {
    expect(layoutWeeks([1, 0, 0, 2, 0, 0, 0, 1], 2)).toEqual([
      { type: "week", index: 0 },
      { type: "week", index: 1 },
      { type: "gap", from: 2, weeks: 1 },
      { type: "week", index: 3 },
      { type: "gap", from: 4, weeks: 3 },
      { type: "week", index: 7 },
    ]);
  });

  it("drops empty weeks after the last busy one", () => {
    expect(layoutWeeks([1, 0, 0, 3, 0, 0], 2).map((s) => s.type)).toEqual(["week", "week", "gap", "week"]);
  });

  it("counts the weeks needed to reach the last date", () => {
    expect(weeksUntil("2026-11-16", null)).toBe(5);
    expect(weeksUntil("2026-11-16", "2026-11-22")).toBe(5);
    expect(weeksUntil("2026-11-16", "2027-01-31", 1)).toBe(11);
    expect(weeksUntil("2026-11-16", "2027-02-01", 1)).toBe(12);
  });
});
