"use client";

import { useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { useWorkspace } from "@/lib/workspace";
import styles from "./workspace-admin.module.css";

export function errorMessage(error: unknown) {
  return error instanceof Error
    ? error.message
    : "The change could not be saved. Try again.";
}

export function SaveMessage({
  message,
  error,
}: {
  message?: string;
  error?: string;
}) {
  if (error)
    return (
      <p className={styles.error} role="alert">
        {error}
      </p>
    );
  if (message)
    return (
      <p className={styles.saved} role="status">
        {message}
      </p>
    );
  return null;
}

export function AdminFrame({
  title,
  description,
  children,
  requireAdmin = true,
}: {
  title: string;
  description: string;
  children: ReactNode;
  requireAdmin?: boolean;
}) {
  const { snapshot, status, error, refresh, client } = useWorkspace();
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState("");
  async function changeAdmin() {
    setPending(true);
    setActionError("");
    try {
      if (snapshot?.admin.active) await client.leaveAdminSimulation();
      else await client.enterAdminSimulation();
      await refresh();
    } catch (cause) {
      setActionError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }
  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <p className={styles.eyebrow}>WORKSPACE / {title.toUpperCase()}</p>
        <h1>{title}</h1>
        <p className={styles.intro}>{description}</p>
      </header>
      {status === "loading" && !snapshot ? (
        <p role="status" className={styles.notice}>
          Loading workspace…
        </p>
      ) : null}
      {error ? (
        <div className={styles.notice}>
          <p role="alert">{error}</p>
          <Button variant="secondary" onClick={() => void refresh()}>
            Try again
          </Button>
        </div>
      ) : null}
      {snapshot ? (
        <>
          <section
            className={styles.demoAccess}
            aria-label="Administration access"
          >
            <div>
              <strong>
                {snapshot.admin.active
                  ? "Demo administration active"
                  : "Routine shared access"}
              </strong>
              <p>
                {snapshot.admin.active
                  ? "Changes are saved to the local demo workspace. This is a simulation, not authenticated administrative access."
                  : "Routine staff do not need a personal account. Enter the demo administration to manage this synthetic workspace."}
              </p>
            </div>
            <Button
              variant="secondary"
              pending={pending}
              onClick={() => void changeAdmin()}
            >
              {snapshot.admin.active
                ? "Leave demo administration"
                : "Enter demo administration"}
            </Button>
          </section>
          <SaveMessage error={actionError} />
          {!snapshot.persistence.available ? (
            <p role="alert" className={styles.notice}>
              {snapshot.persistence.message}
            </p>
          ) : null}
          {requireAdmin && !snapshot.admin.active ? (
            <section className={styles.gate}>
              <span className={styles.sectionNumber}>01</span>
              <div>
                <h2>Administration is separate from daily care</h2>
                <p>
                  Facility changes, imports and shared-client permissions
                  require administrative access. Leaving administration
                  preserves an approved station’s routine use.
                </p>
                <p className={styles.muted}>
                  Email sign-in, verification and recovery need a production
                  authentication service. No personal credentials are collected
                  in this demo.
                </p>
              </div>
            </section>
          ) : (
            children
          )}
        </>
      ) : null}
    </div>
  );
}

export function SectionHeading({
  number,
  title,
  description,
}: {
  number: string;
  title: string;
  description?: string;
}) {
  return (
    <div className={styles.sectionHeading}>
      <span className={styles.sectionNumber}>{number}</span>
      <div>
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
    </div>
  );
}
