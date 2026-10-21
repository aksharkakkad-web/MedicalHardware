/** Local synthetic demo limits, not production upload limits. */
export const DEMO_CSV_MAX_BYTES = 100000;
export const DEMO_CSV_MAX_ROWS = 100;
/** RFC 4180 style quoted fields; the result is data and is never evaluated. */
export function parseRosterCsv(csv: string): {
  headers: string[];
  rows: string[][];
} {
  if (new TextEncoder().encode(csv).length > DEMO_CSV_MAX_BYTES)
    throw new Error("Demo CSV must be 100,000 bytes or smaller.");
  const records: string[][] = [];
  let row: string[] = [];
  let value = "";
  let quoted = false;
  const source = csv.replace(/^\uFEFF/, "");
  for (let i = 0; i < source.length; i++) {
    const ch = source[i];
    if (ch === '"') {
      if (quoted && source[i + 1] === '"') {
        value += '"';
        i++;
      } else if (quoted || value === "") quoted = !quoted;
      else throw new Error("CSV contains an unexpected quote.");
    } else if (!quoted && (ch === "," || ch === "\n" || ch === "\r")) {
      row.push(value.trim());
      value = "";
      if (ch !== ",") {
        if (row.some(Boolean)) records.push(row);
        row = [];
        if (ch === "\r" && source[i + 1] === "\n") i++;
      }
    } else value += ch;
  }
  if (quoted) throw new Error("CSV contains an unclosed quoted field.");
  row.push(value.trim());
  if (row.some(Boolean)) records.push(row);
  const headers = records.shift() ?? [];
  if (records.length > DEMO_CSV_MAX_ROWS)
    throw new Error("Demo CSV supports at most 100 resident rows.");
  if (new Set(headers.map((h) => h.toLowerCase())).size !== headers.length)
    throw new Error("CSV column names must be unique.");
  return {
    headers,
    rows: records,
  };
}
