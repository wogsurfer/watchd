export type WeekSlot = { type: "week"; index: number } | { type: "gap"; from: number; weeks: number };

/**
 * Which weeks the calendar shows: the first `always` weeks in full (even
 * when empty), then only weeks with something in them, a run of empty weeks
 * between them becoming one gap. Empty weeks after the last busy one are
 * left off.
 */
export function layoutWeeks(itemsPerWeek: number[], always = 5): WeekSlot[] {
  const out: WeekSlot[] = [];
  let lastBusy = -1;
  itemsPerWeek.forEach((n, i) => { if (n > 0) lastBusy = i; });
  const end = Math.max(Math.min(always, itemsPerWeek.length), lastBusy + 1);
  let gapFrom = -1;
  for (let i = 0; i < end; i++) {
    if (i < always || itemsPerWeek[i] > 0) {
      if (gapFrom >= 0) {
        out.push({ type: "gap", from: gapFrom, weeks: i - gapFrom });
        gapFrom = -1;
      }
      out.push({ type: "week", index: i });
    } else if (gapFrom < 0) {
      gapFrom = i;
    }
  }
  return out;
}

/** How many weeks from `weekStart` it takes to reach `lastDay` (both YYYY-MM-DD). */
export function weeksUntil(weekStart: string, lastDay: string | null, minimum = 5): number {
  if (!lastDay || lastDay < weekStart) return minimum;
  const days = Math.round((Date.parse(`${lastDay}T00:00:00Z`) - Date.parse(`${weekStart}T00:00:00Z`)) / 86_400_000);
  return Math.max(minimum, Math.floor(days / 7) + 1);
}
