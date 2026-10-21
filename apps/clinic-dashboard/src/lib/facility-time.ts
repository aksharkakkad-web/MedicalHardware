interface DateParts {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
  millisecond: number;
}
const HOUR = 60 * 60 * 1000;
const formatters = new Map<string, Intl.DateTimeFormat>();
function formatter(timeZone: string): Intl.DateTimeFormat | null {
  try {
    let value = formatters.get(timeZone);
    if (!value) {
      value = new Intl.DateTimeFormat("en-US", {
        timeZone,
        calendar: "gregory",
        numberingSystem: "latn",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hourCycle: "h23"
      });
      formatters.set(timeZone, value);
    }
    return value;
  } catch {
    return null;
  }
}
function parseLocal(local: string): DateParts | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?$/.exec(local);
  if (!match) return null;
  const [, y, mo, d, h, mi, s = "0", ms = "0"] = match;
  const result = {
    year: Number(y),
    month: Number(mo),
    day: Number(d),
    hour: Number(h),
    minute: Number(mi),
    second: Number(s),
    millisecond: Number(ms.padEnd(3, "0"))
  };
  const leap = result.year % 4 === 0 && (result.year % 100 !== 0 || result.year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (result.year < 1 || result.month < 1 || result.month > 12 || result.day < 1 || result.day > days[result.month - 1] || result.hour > 23 || result.minute > 59 || result.second > 59) return null;
  return result;
}
function utc(parts: DateParts): number {
  const result = new Date(0);
  result.setUTCFullYear(parts.year, parts.month - 1, parts.day);
  result.setUTCHours(parts.hour, parts.minute, parts.second, parts.millisecond);
  return result.getTime();
}
function zonedParts(epoch: number, format: Intl.DateTimeFormat): DateParts {
  const parts = Object.fromEntries(format.formatToParts(new Date(epoch)).map(part => [part.type, part.value]));
  return {
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
    hour: Number(parts.hour),
    minute: Number(parts.minute),
    second: Number(parts.second),
    millisecond: 0
  };
}
function sameLocal(a: DateParts, b: DateParts) {
  return a.year === b.year && a.month === b.month && a.day === b.day && a.hour === b.hour && a.minute === b.minute && a.second === b.second;
}
function absolute(iso: string): Date | null {
  const match = /^(.+)(Z|[+-]\d{2}:\d{2})$/.exec(iso);
  if (!match || !parseLocal(match[1])) return null;
  if (match[2] !== "Z") {
    const [hours, minutes] = match[2].slice(1).split(":").map(Number);
    if (hours > 23 || minutes > 59) return null;
  }
  const result = new Date(iso);
  return Number.isFinite(result.getTime()) ? result : null;
}

/** Display an explicit instant at minute precision in the facility's zone. No browser-local parsing. */
export function facilityDateTimeInputValue(iso: string, timeZone: string): string {
  const value = absolute(iso),
    format = formatter(timeZone);
  if (!value || !format) return "";
  const parts = zonedParts(value.getTime(), format);
  const pad = (number: number, length = 2) => String(number).padStart(length, "0");
  return `${pad(parts.year, 4)}-${pad(parts.month)}-${pad(parts.day)}T${pad(parts.hour)}:${pad(parts.minute)}`;
}

/** Zero candidates means invalid/nonexistent wall time; two candidates require a deliberate DST choice. */
export function facilityDateTimeCandidates(local: string, timeZone: string): string[] {
  const requested = parseLocal(local),
    format = formatter(timeZone);
  if (!requested || !format) return [];
  const naive = utc(requested);
  const offsets = new Set<number>();
  // Sample both sides of any nearby modern IANA offset transition, including half-hour DST.
  for (let hours = -36; hours <= 36; hours += 3) {
    const probe = naive + hours * HOUR;
    const localAtProbe = zonedParts(probe, format);
    offsets.add(utc(localAtProbe) - Math.floor(probe / 1000) * 1000);
  }
  const candidates = [...offsets].map(offset => naive - offset).filter(epoch => sameLocal(requested, zonedParts(epoch, format)));
  return [...new Set(candidates)].sort((a, b) => a - b).map(epoch => new Date(epoch).toISOString());
}
