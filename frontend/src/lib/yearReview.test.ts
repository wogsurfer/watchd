import { describe, expect, it } from "vitest";
import type { PhysicalSummary } from "./api";
import { addUp, discsAddedIn, mergeSources, peak, topCast } from "./yearReview";

describe("year in review", () => {
  it("merges film and TV sources and counts the unrecorded rest", () => {
    const out = mergeSources(
      [[{ name: "Netflix", count: 10 }, { name: "Blu-ray", count: 5 }], [{ name: "Blu-ray", count: 15 }]],
      50,
    );
    expect(out).toEqual([
      { name: "Blu-ray", count: 20, pct: 40 },
      { name: "Not recorded", count: 20, pct: 40 },
      { name: "Netflix", count: 10, pct: 20 },
    ]);
  });

  it("adds arrays and finds the peak", () => {
    expect(addUp([1, 2, 0], [3, 0, 0])).toEqual([4, 2, 0]);
    expect(peak([0, 3, 5, 5])).toBe(2);
    expect(peak([0, 0])).toBe(-1);
  });

  it("puts actors and actresses together, most titles first", () => {
    const p = (name: string, movies: number, shows = 0, episodes = 0) => ({ name, movies, shows, episodes });
    const out = topCast({ actors: [p("A", 2), p("B", 1, 1, 9)], actresses: [p("C", 3), p("D", 1, 1, 2)] }, 3);
    expect(out.map((x) => x.name)).toEqual(["C", "B", "D"]);
  });

  it("counts discs bought in the year, a box set once", () => {
    const d = (id: number, extra: Partial<PhysicalSummary>) => ({ id, status: "owned", title: `#${id}`, ...extra }) as PhysicalSummary;
    const items = [
      d(1, { purchase_date: "2026-03-01" }),
      d(2, { purchase_date: "2025-12-31" }),
      d(3, { date_added: "2026-07-07T10:00:00" }),
      d(4, { purchase_date: "2026-05-05", is_set: true }),
      d(5, { purchase_date: "2026-05-05", parent_id: 4 }),
      d(6, { purchase_date: "2026-08-08", status: "wishlist" }),
    ];
    expect(discsAddedIn(items, 2026).map((i) => i.id)).toEqual([3, 4, 1]);
  });
});
