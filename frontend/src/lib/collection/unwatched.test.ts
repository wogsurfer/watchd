import { describe, expect, it } from "vitest";
import type { PhysicalSummary } from "../api";
import { shelfAge, unwatchedOnShelf } from "./unwatched";

let nextId = 1;
const disc = (title: string, extra: Partial<PhysicalSummary> = {}): PhysicalSummary =>
  ({ id: nextId++, status: "owned", title, ...extra }) as PhysicalSummary;
const TODAY = new Date(2026, 10, 18); // 18 November 2026
const titles = (items: PhysicalSummary[]) => unwatchedOnShelf(items, TODAY).map((w) => w.item.title);

describe("unwatched on the shelf", () => {
  it("lists owned films never played, longest on the shelf first", () => {
    const items = [
      disc("Newer", { purchase_date: "2025-06-01" }),
      disc("Oldest", { purchase_date: "2012-03-04" }),
      disc("Seen", { purchase_date: "2010-01-01", seen: true }),
      disc("Wanted", { status: "wishlist", purchase_date: "2009-01-01" }),
      disc("Middle", { purchase_date: "2019-09-09" }),
    ];
    expect(titles(items)).toEqual(["Oldest", "Middle", "Newer"]);
  });

  it("leaves out series and the box sets themselves, but keeps the films inside", () => {
    const set = disc("Trilogy", { is_set: true, purchase_date: "2014-05-05" });
    const items = [
      set,
      disc("Part One", { parent_id: set.id }),
      disc("Part Two", { parent_id: set.id, seen: true }),
      disc("A Series", { is_tv: true, tmdb_kind: "tv", purchase_date: "2011-01-01" }),
    ];
    const out = unwatchedOnShelf(items, TODAY);
    expect(out.map((w) => w.item.title)).toEqual(["Part One"]);
    // A film in a set takes the set's purchase date.
    expect(out[0].since).toBe("2014-05-05");
  });

  it("falls back to the day it was added, and puts undated discs last", () => {
    const out = unwatchedOnShelf([
      disc("No date"),
      disc("Added", { date_added: "2020-02-02T10:00:00" }),
    ], TODAY);
    expect(out.map((w) => [w.item.title, w.since])).toEqual([["Added", "2020-02-02"], ["No date", null]]);
    expect(out[1].days).toBeNull();
  });

  it("counts the days on the shelf", () => {
    const [w] = unwatchedOnShelf([disc("Week", { purchase_date: "2026-11-11" })], TODAY);
    expect(w.days).toBe(7);
  });
});

describe("shelf age", () => {
  it("reads naturally", () => {
    expect(shelfAge(null)).toBe("Date unknown");
    expect(shelfAge(0)).toBe("Today");
    expect(shelfAge(1)).toBe("1 day");
    expect(shelfAge(20)).toBe("20 days");
    expect(shelfAge(45)).toBe("1 month");
    expect(shelfAge(365)).toBe("1 year");
    expect(shelfAge(400)).toBe("1 year, 1 month");
    expect(shelfAge(3 * 365 + 70)).toBe("3 years, 2 months");
  });
});
