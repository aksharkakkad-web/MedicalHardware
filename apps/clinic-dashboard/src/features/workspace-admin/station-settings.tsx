"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import {
  useWorkspace,
  type CareArea,
  type SharedClient,
  type WorkspacePermission,
} from "@/lib/workspace";
import {
  AdminFrame,
  errorMessage,
  SaveMessage,
  SectionHeading,
} from "./admin-common";
import styles from "./workspace-admin.module.css";

const permissionChoices: ReadonlyArray<{
  value: WorkspacePermission;
  label: string;
}> = [
  { value: "acknowledge", label: "Acknowledge concerns" },
  { value: "record_check", label: "Record resident checks" },
  { value: "resolve_concern", label: "Resolve concerns" },
  { value: "add_follow_up", label: "Add follow-up" },
  { value: "update_follow_up", label: "Complete or hand over follow-up" },
  { value: "report_context", label: "Report resident context" },
];

function PermissionChoices({
  selected,
  onChange,
  legend,
  disabled,
}: {
  selected: WorkspacePermission[];
  onChange: (permissions: WorkspacePermission[]) => void;
  legend: string;
  disabled?: boolean;
}) {
  return (
    <fieldset className={styles.permissionChoices} disabled={disabled}>
      <legend>{legend}</legend>
      {permissionChoices.map((permission) => (
        <label key={permission.value}>
          <input
            type="checkbox"
            checked={selected.includes(permission.value)}
            onChange={(event) =>
              onChange(
                event.target.checked
                  ? [...selected, permission.value]
                  : selected.filter((item) => item !== permission.value),
              )
            }
          />
          <span>{permission.label}</span>
        </label>
      ))}
    </fieldset>
  );
}

function AreaChoices({
  areas,
  selected,
  onChange,
  legend,
  disabled,
}: {
  areas: CareArea[];
  selected: string[];
  onChange: (ids: string[]) => void;
  legend: string;
  disabled?: boolean;
}) {
  return (
    <fieldset className={styles.areaChoices} disabled={disabled}>
      <legend>{legend}</legend>
      {areas.map((area) => (
        <label key={area.areaId}>
          <input
            type="checkbox"
            checked={selected.includes(area.areaId)}
            onChange={(event) =>
              onChange(
                event.target.checked
                  ? [...selected, area.areaId]
                  : selected.filter((id) => id !== area.areaId),
              )
            }
          />
          <span>{area.name}</span>
        </label>
      ))}
    </fieldset>
  );
}

function StationEditor({
  station,
  areas,
  current,
}: {
  station: SharedClient;
  areas: CareArea[];
  current: boolean;
}) {
  const { client, refresh } = useWorkspace();
  const [name, setName] = useState(station.name);
  const [areaIds, setAreaIds] = useState(station.areaIds);
  const [permissions, setPermissions] = useState<WorkspacePermission[]>(
    station.permissions ?? [],
  );
  const [configurationVersion, setConfigurationVersion] = useState(
    station.configurationVersion,
  );
  const [confirmRevoke, setConfirmRevoke] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const settingsChanged = configurationVersion !== station.configurationVersion;
  function loadCurrentSettings() {
    setName(station.name);
    setAreaIds(station.areaIds);
    setPermissions(station.permissions);
    setConfigurationVersion(station.configurationVersion);
    setConfirmRevoke(false);
    setMessage("");
    setError("");
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (settingsChanged) {
      setError(
        "Station settings changed. Load current station settings before saving.",
      );
      return;
    }
    setPending(true);
    setError("");
    setMessage("");
    try {
      const saved = await client.updateClient({
        clientId: station.clientId,
        name: name.trim(),
        areaIds,
        permissions,
        expectedConfigurationVersion: configurationVersion,
      });
      setName(saved.name);
      setAreaIds(saved.areaIds);
      setPermissions(saved.permissions);
      setConfigurationVersion(saved.configurationVersion);
      await refresh();
      setMessage("Station settings saved.");
    } catch (cause) {
      setError(errorMessage(cause));
      await refresh();
    } finally {
      setPending(false);
    }
  }
  async function revoke() {
    setPending(true);
    setError("");
    setMessage("");
    try {
      await client.revokeClient(station.clientId);
      await refresh();
      setConfirmRevoke(false);
      setMessage("Station approval revoked in this demo.");
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }
  return (
    <article
      className={styles.stationRecord}
      aria-label={`Station ${station.name}`}
    >
      <div className={styles.recordHeading}>
        <h3>{station.name}</h3>
        <span>
          {current ? "This station · " : ""}
          {station.status === "approved" ? "Approved" : "Revoked"}
        </span>
      </div>
      <p className={styles.recordId}>{station.clientId}</p>
      {station.status === "approved" ? (
        <form onSubmit={save} className={styles.form}>
          {settingsChanged && !pending ? (
            <div className={styles.notice} role="status">
              <p>
                Station settings changed elsewhere. Your draft is still here.
                Load the current settings before saving; this replaces your
                unsaved name, coverage and action choices.
              </p>
              <Button variant="secondary" onClick={loadCurrentSettings}>
                Load current station settings
              </Button>
            </div>
          ) : null}
          <FormField
            disabled={pending}
            label={`Station name: ${station.name}`}
            required
            value={name}
            maxLength={100}
            onChange={(event) => setName(event.target.value)}
          />
          <AreaChoices
            disabled={pending}
            legend={`Approved coverage: ${station.name}`}
            areas={areas}
            selected={areaIds}
            onChange={setAreaIds}
          />
          <PermissionChoices
            disabled={pending}
            legend={`Permitted actions: ${station.name}`}
            selected={permissions}
            onChange={setPermissions}
          />
          <p className={styles.muted}>
            {permissions.length
              ? "Only the selected response actions are permitted for routine use."
              : "View only. No routine response actions are permitted."}{" "}
            Area coverage and concern visibility stay separate. Entering demo
            administration does not grant routine response actions.
          </p>
          <div className={styles.actions}>
            <Button
              type="submit"
              variant="secondary"
              pending={pending}
              disabled={settingsChanged}
            >
              Save station changes
            </Button>
            <Button
              variant="quiet"
              disabled={pending}
              onClick={() => setConfirmRevoke(true)}
            >
              Revoke approval
            </Button>
          </div>
        </form>
      ) : (
        <p className={styles.muted}>
          This client has no routine access. Approve a new demo client to
          establish another grant.
        </p>
      )}
      {confirmRevoke ? (
        <div
          className={styles.confirmation}
          role="group"
          aria-label={`Confirm revocation for ${station.name}`}
        >
          <strong>Revoke {station.name}?</strong>
          <p>
            {current
              ? "This station’s resident views and response actions will be blocked in the demo."
              : "This client will lose its approved routine coverage in the demo."}{" "}
            Existing action history is retained.
          </p>
          <div className={styles.actions}>
            <Button
              variant="danger"
              pending={pending}
              onClick={() => void revoke()}
            >
              Confirm revocation
            </Button>
            <Button
              variant="secondary"
              disabled={pending}
              onClick={() => setConfirmRevoke(false)}
            >
              Keep approval
            </Button>
          </div>
        </div>
      ) : null}
      <SaveMessage message={settingsChanged ? "" : message} error={error} />
    </article>
  );
}

function ApproveStation({ areas }: { areas: CareArea[] }) {
  const { client, refresh } = useWorkspace();
  const [name, setName] = useState("");
  const [areaIds, setAreaIds] = useState<string[]>([]);
  const [permissions, setPermissions] = useState<WorkspacePermission[]>([]);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!areaIds.length) {
      setError("Select at least one care area before approving a station.");
      return;
    }
    setPending(true);
    try {
      await client.approveClient({ name: name.trim(), areaIds, permissions });
      await refresh();
      setMessage("Shared station approved in this demo.");
      setName("");
      setAreaIds([]);
      setPermissions([]);
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }
  return (
    <form onSubmit={submit} className={styles.form}>
      <FormField
        disabled={pending}
        label="New station name"
        required
        value={name}
        maxLength={100}
        placeholder="For example, North wing tablet"
        onChange={(event) => setName(event.target.value)}
      />
      <AreaChoices
        disabled={pending}
        legend="Coverage for the new station"
        areas={areas}
        selected={areaIds}
        onChange={setAreaIds}
      />
      <PermissionChoices
        disabled={pending}
        legend="Permitted actions for the new station"
        selected={permissions}
        onChange={setPermissions}
      />
      <p className={styles.muted}>
        New stations start with view-only access. Select any routine actions
        this shared client may perform. No personal staff login is required.
        Action permissions do not mute concerns or change area coverage.
      </p>
      <p className={styles.muted}>
        Creates a local demo client record. Secure enrollment, credentials,
        expiry and server-enforced authorization require the production access
        service.
      </p>
      <div className={styles.formFooter}>
        <Button type="submit" pending={pending}>
          Approve demo station
        </Button>
        <SaveMessage message={message} error={error} />
      </div>
    </form>
  );
}

export function StationSettings() {
  const { snapshot, client, refresh } = useWorkspace();
  const [testing, setTesting] = useState(false);
  const [testMessage, setTestMessage] = useState("");
  const [testError, setTestError] = useState("");
  const [switchError, setSwitchError] = useState("");
  async function testNotifications() {
    setTesting(true);
    setTestMessage("");
    setTestError("");
    try {
      const result = await client.testNotifications();
      await refresh();
      setTestMessage(`No notification was delivered. ${result.reason}`);
    } catch (cause) {
      setTestError(errorMessage(cause));
    } finally {
      setTesting(false);
    }
  }
  async function switchClient(clientId: string) {
    setSwitchError("");
    setTestMessage("");
    try {
      await client.selectDemoClient(clientId);
      await refresh();
    } catch (cause) {
      setSwitchError(errorMessage(cause));
    }
  }
  return (
    <AdminFrame
      title="Shared stations"
      description="Routine access belongs to an approved shared client and its coverage. A recorded action identifies the station, not an individual caregiver."
      requireAdmin={false}
    >
      {snapshot ? (
        <>
          <section className={styles.section}>
            <SectionHeading
              number="01"
              title="This shared station"
              description="Coverage stays the same when a laptop or tablet moves. An administrator must change the approved area."
            />
            <dl className={styles.details}>
              <div>
                <dt>Station</dt>
                <dd>{snapshot.currentClient.name}</dd>
              </div>
              <div>
                <dt>Access</dt>
                <dd>
                  {snapshot.currentClient.status === "approved"
                    ? "Approved for routine use in this demo"
                    : "Revoked — resident access blocked"}
                </dd>
              </div>
              <div>
                <dt>Coverage</dt>
                <dd>
                  {snapshot.currentClient.areaIds
                    .map(
                      (id) =>
                        snapshot.areas.find((area) => area.areaId === id)
                          ?.name ?? "Unknown area",
                    )
                    .join(", ") || "No approved coverage"}
                </dd>
              </div>
              <div>
                <dt>Routine actions</dt>
                <dd>
                  {snapshot.currentClient.status !== "approved"
                    ? "None — station approval is revoked"
                    : permissionChoices
                        .filter((permission) =>
                          snapshot.currentClient.permissions?.includes(
                            permission.value,
                          ),
                        )
                        .map((permission) => permission.label)
                        .join(", ") || "View only — no response actions"}
                </dd>
              </div>
              <div>
                <dt>Attribution</dt>
                <dd>
                  Station, action record and time. Individual caregiver identity
                  is not verified.
                </dd>
              </div>
            </dl>
            <p className={styles.muted}>
              Area coverage controls which residents and concerns are visible.
              Action rights control responses; notification readiness and actual
              delivery remain separate.
            </p>
          </section>
          <section className={styles.section}>
            <SectionHeading
              number="02"
              title="Notification readiness"
              description="A visible dashboard does not establish unattended alert delivery."
            />
            <div className={styles.readiness}>
              <span className={styles.readinessMark} aria-hidden="true">
                !
              </span>
              <div>
                <h3>Delivery service is not connected</h3>
                <p>
                  Background alerts, browser push subscriptions and an
                  independent escalation destination need backend and platform
                  integration. Closing all browsers is not a tested delivery
                  path in this demo.
                </p>
              </div>
            </div>
            <Button
              variant="secondary"
              pending={testing}
              disabled={snapshot.currentClient.status !== "approved"}
              onClick={() => void testNotifications()}
            >
              Check notification readiness
            </Button>
            {testMessage ? (
              <p role="status" className={styles.notice}>
                {testMessage}
              </p>
            ) : null}
            <SaveMessage error={testError} />
          </section>
          {snapshot.admin.active ? (
            <>
              <section className={styles.section}>
                <SectionHeading
                  number="03"
                  title="Approved clients"
                  description="A deliberate grant may include more than one care area. A view filter never expands that grant."
                />
                <div className={styles.stationList}>
                  {snapshot.clients.map((station) => (
                    <StationEditor
                      key={station.clientId}
                      station={station}
                      areas={snapshot.areas}
                      current={
                        snapshot.currentClient.clientId === station.clientId
                      }
                    />
                  ))}
                </div>
              </section>
              <section className={styles.section}>
                <SectionHeading
                  number="04"
                  title="Approve a shared station"
                  description="Give each shared client a recognizable name and explicit coverage."
                />
                <ApproveStation areas={snapshot.areas} />
              </section>
              <section className={styles.section}>
                <SectionHeading
                  number="05"
                  title="Demo station perspective"
                  description="Inspect another local demo station. This selection is not production enrollment or authentication."
                />
                <FormField
                  as="select"
                  label="View as demo station"
                  value={snapshot.currentClient.clientId}
                  onChange={(event) => void switchClient(event.target.value)}
                  options={snapshot.clients.map((station) => ({
                    value: station.clientId,
                    label: `${station.name}${station.status === "revoked" ? " · revoked" : ""}`,
                  }))}
                />
                <SaveMessage error={switchError} />
              </section>
            </>
          ) : (
            <p className={styles.muted}>
              Enter demo administration above to approve clients or change their
              coverage.
            </p>
          )}
        </>
      ) : null}
    </AdminFrame>
  );
}
