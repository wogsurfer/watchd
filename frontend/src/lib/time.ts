// Watch times come from the API as naive UTC ("2026-10-18T13:00:00"). Pages
// render them in a <time data-local="date|time"> element: the server formats it
// in the install's home time zone (its TZ setting), then Base.astro
// re-formats it in the browser's own zone, matching the Watch History popup.

/** Use this as `timeZone` for any date/time formatted during server rendering. */
export const HOME_TIME_ZONE = (typeof process !== "undefined" && process.env?.TZ) || "UTC";

/**
 * Where watches were logged before a move (WATCHD_EARLIER_HOME, e.g.
 * "Perth:2015-10-25"): their times are that place's clock, so they're tagged
 * with its name. Read during server rendering; Base.astro hands it to the
 * browser as <html data-earlier-home="Perth|2015-10-25">.
 */
export interface EarlierHome { name: string; until: string }
export const EARLIER_HOME: EarlierHome | null = (() => {
  const raw = typeof process !== "undefined" ? process.env?.WATCHD_EARLIER_HOME : undefined;
  const m = raw?.match(/^(.+):(\d{4}-\d{2}-\d{2})$/);
  return m ? { name: m[1].trim(), until: m[2] } : null;
})();

/** The earlier home's name when this watch (naive UTC) was before the move. */
export function earlierHomeOf(value: string | null | undefined, home: EarlierHome | null = EARLIER_HOME): string | null {
  if (!value || !home) return null;
  return utcIso(value) < `${home.until}T00:00:00Z` ? home.name : null;
}

/** Mark a naive UTC timestamp as UTC so Date parses it correctly anywhere. */
export function utcIso(value: string): string {
  // Postgres gives microseconds; some browsers (Safari) only parse milliseconds.
  const trimmed = value.replace(/(\.\d{3})\d+/, "$1");
  return /(Z|[+-]\d\d:?\d\d)$/.test(trimmed) ? trimmed : `${trimmed}Z`;
}

export const WATCH_DATE_FORMAT: Intl.DateTimeFormatOptions = {
  month: "short",
  day: "numeric",
  year: "numeric",
};

/** All times in the app are shown in 24-hour format (e.g. 23:31). */
export const WATCH_TIME_FORMAT: Intl.DateTimeFormatOptions = {
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
};

export function formatWatchDate(value: string): string {
  return new Date(utcIso(value)).toLocaleDateString("en-US", {
    ...WATCH_DATE_FORMAT,
    timeZone: HOME_TIME_ZONE,
  });
}

export function formatWatchTime(value: string): string {
  return new Date(utcIso(value)).toLocaleTimeString("en-US", {
    ...WATCH_TIME_FORMAT,
    timeZone: HOME_TIME_ZONE,
  });
}
