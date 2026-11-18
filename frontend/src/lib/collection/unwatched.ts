import type { PhysicalSummary } from "../api";

export interface ShelfWait {
  item: PhysicalSummary;
  /** The day it reached the shelf: bought, else added to Watchd (YYYY-MM-DD). */
  since: string | null;
  /** Whole days since then. */
  days: number | null;
}

const day = (value?: string | null) => (value ? String(value).slice(0, 10) : null);

/**
 * Films you own on disc and have never played (in Watchd, or marked seen in
 * Collectorz), longest on the shelf first. A box set is looked at film by
 * film, each one taking the set's purchase date when it has none of its own.
 * Series are left out: a series disc has no single play to look for.
 */
export function unwatchedOnShelf(items: PhysicalSummary[], today: Date = new Date()): ShelfWait[] {
  const byId = new Map(items.map((i) => [i.id, i]));
  const now = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  const out: ShelfWait[] = [];
  for (const item of items) {
    if (item.status !== "owned" || item.is_set || item.is_tv || item.tmdb_kind === "tv" || item.seen) continue;
    const parent = item.parent_id ? byId.get(item.parent_id) : undefined;
    if (parent && parent.status !== "owned") continue;
    const since =
      day(item.purchase_date) ?? day(parent?.purchase_date) ?? day(item.date_added) ?? day(parent?.date_added);
    let days: number | null = null;
    if (since) {
      const [y, m, d] = since.split("-").map(Number);
      days = Math.max(0, Math.round((now - Date.UTC(y, m - 1, d)) / 86_400_000));
    }
    out.push({ item, since, days });
  }
  // Oldest first; undated at the end, then by title.
  return out.sort((a, b) => {
    if (a.since !== b.since) {
      if (!a.since) return 1;
      if (!b.since) return -1;
      return a.since < b.since ? -1 : 1;
    }
    return (a.item.sort_title ?? a.item.title).localeCompare(b.item.sort_title ?? b.item.title);
  });
}

/** "3 years, 2 months", "5 months", "12 days", "today". */
export function shelfAge(days: number | null): string {
  if (days == null) return "Date unknown";
  if (days === 0) return "Today";
  if (days < 31) return `${days} day${days === 1 ? "" : "s"}`;
  // A month as 30.4 days, so 365 days reads as a year.
  const months = Math.floor(days / 30.4);
  const years = Math.floor(months / 12);
  const rest = months % 12;
  const part = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;
  if (!years) return part(months, "month");
  return rest ? `${part(years, "year")}, ${part(rest, "month")}` : part(years, "year");
}
