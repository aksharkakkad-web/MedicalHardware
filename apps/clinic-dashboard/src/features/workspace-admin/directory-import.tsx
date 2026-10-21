"use client";

import { useMemo, useState, type ChangeEvent, type FormEvent } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import {
  DEMO_CSV_MAX_BYTES,
  DEMO_CSV_MAX_ROWS,
  parseRosterCsv,
  useWorkspace,
  type RosterColumnMapping,
  type RosterImportPreview,
} from "@/lib/workspace";
import {
  AdminFrame,
  errorMessage,
  SaveMessage,
  SectionHeading,
} from "./admin-common";
import styles from "./workspace-admin.module.css";

const columns = [
  {
    key: "facilityResidentId",
    label: "Resident identifier column",
    aliases: ["facilityresidentid", "resident_id"],
  },
  {
    key: "name",
    label: "Resident name column",
    aliases: ["name", "resident_name"],
  },
  { key: "roomLabel", label: "Room column", aliases: ["roomlabel", "room"] },
  { key: "areaName", label: "Care area column", aliases: ["areaname", "area"] },
] as const;

function readUtf8(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () =>
      reject(
        new Error(
          "The file could not be read. Choose it again or paste CSV contents.",
        ),
      );
    reader.onload = () => {
      try {
        resolve(
          new TextDecoder("utf-8", { fatal: true }).decode(
            reader.result as ArrayBuffer,
          ),
        );
      } catch {
        reject(
          new Error(
            "The roster must be UTF-8 text. Export it as UTF-8 CSV and try again.",
          ),
        );
      }
    };
    reader.readAsArrayBuffer(file);
  });
}

function Preview({ preview }: { preview: RosterImportPreview }) {
  return (
    <div className={styles.preview}>
      <div className={styles.previewHeading}>
        <div>
          <h3>{preview.fileName}</h3>
          <p>
            {preview.rows.length} resident{" "}
            {preview.rows.length === 1 ? "row" : "rows"} ·{" "}
            {preview.status === "applied"
              ? "Applied"
              : preview.canApply
                ? "Ready for review"
                : "Review required"}
          </p>
        </div>
        <span className={styles.recordId}>LOCAL DEMO</span>
      </div>
      {!preview.rows.length ? (
        <p className={styles.notice}>
          No resident rows found. Add a header row and at least one resident.
        </p>
      ) : (
        <div
          className={styles.tableScroll}
          tabIndex={0}
          role="region"
          aria-label="Roster preview table"
        >
          <table className={styles.table}>
            <caption className={styles.srOnly}>
              Proposed directory changes. Review every row before applying.
            </caption>
            <thead>
              <tr>
                <th scope="col">Row</th>
                <th scope="col">Resident</th>
                <th scope="col">Room / area</th>
                <th scope="col">Proposed change</th>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((row) => (
                <tr key={row.rowNumber}>
                  <td data-label="Source row">{row.rowNumber}</td>
                  <td data-label="Resident">
                    <strong>{row.name || "Missing resident name"}</strong>
                    <span className={styles.cellMeta}>
                      {row.facilityResidentId || "Missing identifier"}
                    </span>
                  </td>
                  <td data-label="Room / area">
                    {row.roomLabel || "Missing room"}
                    <span className={styles.cellMeta}>
                      {row.areaName || "Missing area"}
                    </span>
                  </td>
                  <td data-label="Proposed change">
                    <strong>
                      {row.action === "blocked"
                        ? "Blocked"
                        : row.action === "update"
                          ? "Update existing record"
                          : "Add resident"}
                    </strong>
                    {row.issues.map((issue, index) => (
                      <span
                        key={`${index}-${issue}`}
                        className={styles.rowIssue}
                      >
                        {issue}
                      </span>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function DirectoryImport() {
  const { snapshot, client, refresh } = useWorkspace();
  const [csv, setCsv] = useState("");
  const [fileName, setFileName] = useState("Pasted roster.csv");
  const [mapping, setMapping] = useState<RosterColumnMapping>({});
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const parsed = useMemo(() => {
    try {
      return {
        headers: parseRosterCsv(csv).headers.filter((header) => header.trim()),
        error: "",
      };
    } catch (cause) {
      return { headers: [] as string[], error: errorMessage(cause) };
    }
  }, [csv]);
  const resolvedMapping: RosterColumnMapping = Object.fromEntries(
    columns.map((column) => [
      column.key,
      mapping[column.key] ??
        parsed.headers.find((header) =>
          column.aliases.some((alias) => alias === header.toLowerCase()),
        ) ??
        "",
    ]),
  );
  const preview = snapshot?.imports.find((item) => item.importId === previewId);
  function changeCsv(value: string) {
    setCsv(value);
    setDirty(true);
    setMessage("");
    setError("");
    setMapping({});
  }
  async function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    setMessage("");
    setDirty(true);
    if (!/\.csv$/i.test(file.name)) {
      setError(
        "Only UTF-8 CSV is available in this demo. XLSX and PDF processing need the backend import service.",
      );
      return;
    }
    if (file.size > DEMO_CSV_MAX_BYTES) {
      setError(
        `The local demo accepts files up to ${DEMO_CSV_MAX_BYTES.toLocaleString()} bytes.`,
      );
      return;
    }
    setPending(true);
    try {
      changeCsv(await readUtf8(file));
      setFileName(file.name);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }
  async function review(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!csv.trim()) {
      setError("Choose a CSV file or paste the roster before review.");
      return;
    }
    if (parsed.error) {
      setError(parsed.error);
      return;
    }
    const chosen = Object.values(resolvedMapping);
    if (chosen.some((header) => !header) || chosen.length !== columns.length) {
      setError("Map all four required columns before reviewing the roster.");
      return;
    }
    if (new Set(chosen).size !== chosen.length) {
      setError("Choose a different source column for each required field.");
      return;
    }
    setPending(true);
    try {
      const result = await client.previewRosterCsv(
        csv,
        fileName,
        resolvedMapping,
      );
      await refresh();
      setPreviewId(result.importId);
      setDirty(false);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }
  async function apply() {
    if (!preview || dirty) return;
    setPending(true);
    setError("");
    setMessage("");
    try {
      await client.applyRosterImport(preview.importId);
      await refresh();
      setMessage("Roster applied to this demo workspace.");
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }
  return (
    <AdminFrame
      title="Directory import"
      description="Map a roster, inspect every proposed change, then apply it explicitly. Existing records stay intact when validation fails."
    >
      {snapshot ? (
        <>
          <section className={styles.section}>
            <SectionHeading
              number="01"
              title="Prepare the roster"
              description="Use synthetic records here. Files are read locally; this is not a private server upload service."
            />
            <div className={styles.importGuide}>
              <div>
                <h3>UTF-8 CSV</h3>
                <p>
                  Required: stable resident identifier, resident name, room
                  label and care area name. Match an existing area exactly. Room
                  labels are not resident identities.
                </p>
                <p className={styles.muted}>
                  Local demo limits: {DEMO_CSV_MAX_BYTES.toLocaleString()} bytes
                  and {DEMO_CSV_MAX_ROWS} resident rows. Effective assignment
                  time is the local demo application time; per-row effective
                  dates are not supported.
                </p>
              </div>
              <pre className={styles.csvExample}>
                <code>{`facilityResidentId,name,roomLabel,areaName\nDEMO-900,Synthetic Resident,900,${snapshot.areas.find((area) => area.areaId === snapshot.currentAreaId)?.name ?? snapshot.areas.find((area) => snapshot.currentClient.areaIds.includes(area.areaId))?.name ?? snapshot.areas[0]?.name ?? "Care area name"}`}</code>
              </pre>
            </div>
            <form onSubmit={review} className={styles.form}>
              <FormField
                label="Choose a CSV roster"
                type="file"
                accept=".csv,text/csv"
                disabled={pending}
                onChange={(event) => void chooseFile(event)}
                hint="The file stays in this browser. Use synthetic information only."
              />
              <FormField
                disabled={pending}
                label="CSV contents"
                as="textarea"
                value={csv}
                rows={7}
                placeholder="Paste a header row followed by resident records…"
                onChange={(event) => {
                  changeCsv(event.target.value);
                  setFileName("Pasted roster.csv");
                }}
              />
              {parsed.headers.length ? (
                <fieldset className={styles.mapping}>
                  <legend>Match source columns</legend>
                  <p>Each required field needs its own source column.</p>
                  <div className={styles.fieldGrid}>
                    {columns.map((column) => (
                      <FormField
                        disabled={pending}
                        key={column.key}
                        as="select"
                        label={column.label}
                        value={resolvedMapping[column.key] ?? ""}
                        onChange={(event) => {
                          setMapping({
                            ...resolvedMapping,
                            [column.key]: event.target.value,
                          });
                          setDirty(true);
                          setMessage("");
                        }}
                        options={[
                          { value: "", label: "Choose a column" },
                          ...parsed.headers.map((header) => ({
                            value: header,
                            label: header,
                          })),
                        ]}
                      />
                    ))}
                  </div>
                </fieldset>
              ) : null}
              <div className={styles.formFooter}>
                <Button type="submit" pending={pending}>
                  Review roster
                </Button>
                <SaveMessage error={error} />
              </div>
            </form>
          </section>
          {preview ? (
            <section className={styles.section}>
              <SectionHeading
                number="02"
                title="Review proposed changes"
                description="A preview does not change the resident directory. Blocked rows must be corrected before the complete roster can apply."
              />
              <Preview preview={preview} />
              {dirty ? (
                <p className={styles.notice}>
                  The source or mapping changed. Review the roster again before
                  applying.
                </p>
              ) : null}
              <div className={styles.formFooter}>
                <Button
                  variant="secondary"
                  pending={pending}
                  disabled={
                    dirty || !preview.canApply || preview.status === "applied"
                  }
                  onClick={() => void apply()}
                >
                  Apply reviewed roster
                </Button>
                <SaveMessage message={message} />
              </div>
            </section>
          ) : null}
          {snapshot.imports.length ? (
            <section className={styles.section}>
              <SectionHeading
                number="03"
                title="Local import history"
                description="Saved with the demo workspace when browser storage is available. This is not a durable server job."
              />
              <ul className={styles.history}>
                {[...snapshot.imports].reverse().map((item) => (
                  <li key={item.importId}>
                    <button
                      type="button"
                      disabled={pending}
                      onClick={() => {
                        setPreviewId(item.importId);
                        setDirty(false);
                        setError("");
                        setMessage("");
                      }}
                    >
                      <span>
                        <strong>{item.fileName}</strong>
                        <small>
                          {item.rows.length} rows ·{" "}
                          {new Date(item.createdAt).toLocaleString("en-US", {
                            timeZone: snapshot.facility.timeZone,
                          })}
                        </small>
                      </span>
                      <span>
                        {item.status === "applied"
                          ? "Applied"
                          : item.canApply
                            ? "Ready for review"
                            : "Rejected"}{" "}
                        <span aria-hidden="true">↗</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
          <section className={styles.section}>
            <SectionHeading
              number="04"
              title="Other record sources"
              description="No import is represented as successful without an implemented processing path."
            />
            <div className={styles.capabilityRows}>
              <div>
                <strong>XLSX spreadsheets</strong>
                <p>
                  Not available in this demo. Export a UTF-8 CSV, then map and
                  review it here.
                </p>
              </div>
              <div>
                <strong>PDF medical documents</strong>
                <p>
                  Private storage, text extraction, scan review and
                  source-linked approval require backend services. No PDF
                  extraction runs here.
                </p>
              </div>
              <div>
                <strong>Manual records and context</strong>
                <p>
                  <Link href="/administration">
                    Add or correct a resident record
                  </Link>
                  . Open a resident’s care record to enter dated context; staff
                  observations remain distinct from approved clinical truth.
                </p>
              </div>
            </div>
          </section>
        </>
      ) : null}
    </AdminFrame>
  );
}
