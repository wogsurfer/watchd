import type { PhysicalSummary } from "./api";

export interface Named { name: string; count: number }
export interface Person {
  name: string;
  profile_path?: string | null;
  movies: number;
  shows: number;
  episodes: number;
}

/** Where plays happened, films and TV together, biggest first, with plays
 *  that have no source recorded as "Not recorded". */
export function mergeSources(lists: Named[][], totalPlays: number): (Named & { pct: number })[] {
  const counts = new Map<string, number>();
  for (const list of lists) for (const s of list || []) counts.set(s.name, (counts.get(s.name) || 0) + s.count);
  const known = [...counts.values()].reduce((a, b) => a + b, 0);
  if (totalPlays > known) counts.set("Not recorded", totalPlays - known);
  const total = Math.max(totalPlays, known, 1);
  return [...counts]
    .map(([name, count]) => ({ name, count, pct: Math.round((count / total) * 100) }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}

/** Adds arrays element by element ([1,2] + [3,4] = [4,6]). */
export function addUp(...arrays: number[][]): number[] {
  const len = Math.max(0, ...arrays.map((a) => (a || []).length));
  return Array.from({ length: len }, (_, i) => arrays.reduce((sum, a) => sum + ((a || [])[i] || 0), 0));
}

/** The index of the biggest value (the first on a tie), or -1 if all are 0. */
export function peak(values: number[]): number {
  let best = -1;
  values.forEach((v, i) => { if (v > 0 && (best < 0 || v > values[best])) best = i; });
  return best;
}

/** Actors and actresses together, most titles first. */
export function topCast(people: Record<string, Person[] | undefined>, limit = 6): Person[] {
  return [...(people.actors || []), ...(people.actresses || [])]
    .sort((a, b) => b.movies + b.shows - (a.movies + a.shows) || b.episodes - a.episodes || a.name.localeCompare(b.name))
    .slice(0, limit);
}

/** Releases added to the shelf in a year (bought then, or added to Watchd
 *  then when there's no purchase date), counting a box set once. */
export function discsAddedIn(items: PhysicalSummary[], year: number): PhysicalSummary[] {
  const prefix = String(year);
  return items
    .filter((i) => i.status === "owned" && !i.parent_id)
    .filter((i) => String(i.purchase_date || i.date_added || "").startsWith(prefix))
    .sort((a, b) => String(b.purchase_date || b.date_added).localeCompare(String(a.purchase_date || a.date_added)));
}
