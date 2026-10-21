"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { FormField } from "@/components/ui/form-field";
import { FacilityTimeField } from "@/components/ui/facility-time-field";
import {
  useWorkspace,
  type Facility,
  type CareArea,
  type WorkspaceSnapshot,
} from "@/lib/workspace";
import {
  AdminFrame,
  errorMessage,
  SaveMessage,
  SectionHeading,
} from "./admin-common";
import styles from "./workspace-admin.module.css";

const suggestedTimeZones = [
  { value: "America/Chicago", label: "Central — Chicago" },
  { value: "America/Detroit", label: "Eastern — Detroit" },
  { value: "America/New_York", label: "Eastern — New York" },
  { value: "America/Indiana/Indianapolis", label: "Eastern — Indianapolis" },
  { value: "America/Denver", label: "Mountain — Denver" },
  { value: "America/Phoenix", label: "Arizona — Phoenix" },
  { value: "America/Los_Angeles", label: "Pacific — Los Angeles" },
  { value: "America/Anchorage", label: "Alaska — Anchorage" },
  { value: "Pacific/Honolulu", label: "Hawaii — Honolulu" },
  { value: "UTC", label: "UTC — Coordinated Universal Time" },
];

function FacilityForm({ facility }: { facility: Facility }) {
  const { client, refresh } = useWorkspace();
  const [fields, setFields] = useState(facility);
  const timeZones = suggestedTimeZones.some(
    (zone) => zone.value === facility.timeZone,
  )
    ? suggestedTimeZones
    : [
        {
          value: facility.timeZone,
          label: `${facility.timeZone.split("/").pop()?.replace(/_/g, " ")} — current facility setting`,
        },
        ...suggestedTimeZones,
      ];
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    setMessage("");
    try {
      await client.updateFacility({
        name: fields.name.trim(),
        timeZone: fields.timeZone.trim(),
        coverageContact: fields.coverageContact.trim(),
        escalationContact: fields.escalationContact.trim(),
      });
      await refresh();
      setMessage("Facility details saved in this demo.");
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }
  return (
    <form onSubmit={submit} className={styles.form}>
      <div className={styles.fieldGrid}>
        <FormField
          disabled={pending}
          label="Facility name"
          required
          value={fields.name}
          maxLength={160}
          onChange={(event) =>
            setFields({ ...fields, name: event.target.value })
          }
        />
        <FormField
          as="select"
          disabled={pending}
          label="Facility time zone"
          required
          value={fields.timeZone}
          options={timeZones}
          hint="Choose the time used at this facility. Dates and times follow this setting."
          onChange={(event) =>
            setFields({ ...fields, timeZone: event.target.value })
          }
        />
        <FormField
          disabled={pending}
          label="Coverage contact"
          value={fields.coverageContact}
          maxLength={300}
          hint="A team or duty contact; this does not create a staff account."
          onChange={(event) =>
            setFields({ ...fields, coverageContact: event.target.value })
          }
        />
        <FormField
          disabled={pending}
          label="Escalation contact"
          value={fields.escalationContact}
          maxLength={300}
          hint="Recorded context only. Delivery to this contact is not connected."
          onChange={(event) =>
            setFields({ ...fields, escalationContact: event.target.value })
          }
        />
      </div>
      <div className={styles.formFooter}>
        <Button type="submit" pending={pending} pendingLabel="Saving…">
          Save facility
        </Button>
        <SaveMessage message={message} error={error} />
      </div>
    </form>
  );
}

function AreaForm({ area }: { area?: CareArea }) {
  const { client, refresh } = useWorkspace();
  const [name, setName] = useState(area?.name ?? "");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  async function save(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setMessage("");
    setError("");
    try {
      await client.saveArea({ areaId: area?.areaId, name: name.trim() });
      await refresh();
      setMessage(area ? "Area name saved." : "Care area added.");
      if (!area) setName("");
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setPending(false);
    }
  }
  return (
    <form onSubmit={save} className={styles.areaRow}>
      <FormField
        disabled={pending}
        label={area ? `Area name: ${area.name}` : "New care area"}
        required
        value={name}
        maxLength={100}
        placeholder="For example, North wing"
        onChange={(event) => setName(event.target.value)}
      />
      <Button type="submit" variant="secondary" pending={pending}>
        {area ? "Save area" : "Add area"}
      </Button>
      <SaveMessage message={message} error={error} />
    </form>
  );
}

function ResidentForm({ snapshot }: { snapshot: WorkspaceSnapshot }) {
  const { client, refresh } = useWorkspace();
  const defaultAreaId = snapshot.areas.some(
    (area) => area.areaId === snapshot.currentAreaId,
  )
    ? snapshot.currentAreaId
    : (snapshot.currentClient.areaIds[0] ?? snapshot.areas[0]?.areaId ?? "");
  const [selected, setSelected] = useState("");
  const [name, setName] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [room, setRoom] = useState("");
  const [areaId, setAreaId] = useState(defaultAreaId);
  const [effectiveAt, setEffectiveAt] = useState(() =>
    new Date().toISOString(),
  );
  const [departedAt, setDepartedAt] = useState("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  function selectResident(id: string) {
    setSelected(id);
    setError("");
    setMessage("");
    const profile = snapshot.profiles.find((item) => item.residentId === id);
    setName(profile?.name ?? "");
    setIdentifier(profile?.facilityResidentId ?? "");
    setRoom(profile?.roomLabel ?? "");
    setAreaId(profile?.areaId ?? defaultAreaId);
    setEffectiveAt(new Date().toISOString());
    setDepartedAt(profile?.departedAt ?? "");
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMessage("");
    setPending(true);
    try {
      await client.saveResident({
        residentId: selected || undefined,
        name: name.trim(),
        facilityResidentId: identifier.trim(),
        roomLabel: room.trim(),
        areaId,
        effectiveAt: effectiveAt.trim(),
        departedAt: departedAt.trim() || null,
      });
      await refresh();
      setMessage(
        "Resident record saved in this demo. Assignment history is retained.",
      );
      if (!selected) {
        setName("");
        setIdentifier("");
        setRoom("");
      }
    } catch (cause) {
      const detail = errorMessage(cause);
      setError(
        /ISO date|calendar|time zone/i.test(detail)
          ? "Choose a valid facility date and time. If that time occurs twice, choose which occurrence you mean. No change was saved."
          : detail,
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <form onSubmit={save} className={styles.form}>
      <FormField
        disabled={pending}
        as="select"
        label="Resident record"
        value={selected}
        onChange={(event) => selectResident(event.target.value)}
        options={[
          { value: "", label: "Add a resident" },
          ...snapshot.profiles.map((profile) => ({
            value: profile.residentId,
            label: `${profile.name} · ${profile.roomLabel}`,
          })),
        ]}
      />
      <div className={styles.fieldGrid}>
        <FormField
          disabled={pending}
          label="Resident name"
          required
          value={name}
          maxLength={160}
          onChange={(event) => setName(event.target.value)}
        />
        <FormField
          disabled={pending}
          label="Facility resident identifier"
          required
          value={identifier}
          maxLength={100}
          hint="A stable facility identifier, not a room number."
          onChange={(event) => setIdentifier(event.target.value)}
        />
        <FormField
          disabled={pending}
          as="select"
          label="Care area"
          required
          value={areaId}
          onChange={(event) => setAreaId(event.target.value)}
          options={snapshot.areas.map((area) => ({
            value: area.areaId,
            label: area.name,
          }))}
        />
        <FormField
          disabled={pending}
          label="Room label"
          required
          value={room}
          maxLength={80}
          onChange={(event) => setRoom(event.target.value)}
        />
        <FacilityTimeField
          disabled={pending}
          label="Assignment date and time"
          required
          value={effectiveAt}
          timeZone={snapshot.facility.timeZone}
          hint="When this room assignment took effect."
          onChange={setEffectiveAt}
        />
        {selected ? (
          <FacilityTimeField
            disabled={pending}
            label="Departure date and time (optional)"
            value={departedAt}
            timeZone={snapshot.facility.timeZone}
            hint="Leave empty for a current resident."
            onChange={setDepartedAt}
          />
        ) : null}
      </div>
      <p className={styles.muted}>
        Only records within this station’s approved coverage appear in the
        record selector. New assignments outside that coverage remain outside
        its routine view. Room conflicts require review.
      </p>
      <div className={styles.formFooter}>
        <Button type="submit" variant="secondary" pending={pending}>
          Save resident record
        </Button>
        <SaveMessage message={message} error={error} />
      </div>
    </form>
  );
}

export function FacilityAdmin() {
  const { snapshot } = useWorkspace();
  return (
    <AdminFrame
      title="Administration"
      description="Maintain the facility, care areas and resident directory. Everyday care remains available through approved shared stations."
    >
      {snapshot ? (
        <>
          <section className={styles.section}>
            <SectionHeading
              number="01"
              title="Facility details"
              description="One facility identity. Explicit local time. Clear coverage and escalation context."
            />
            <FacilityForm facility={snapshot.facility} />
          </section>
          <section className={styles.section}>
            <SectionHeading
              number="02"
              title="Care areas"
              description="Areas define shared-client coverage. Renaming an area preserves its identity."
            />
            <div className={styles.areaList}>
              {snapshot.areas.map((area) => (
                <AreaForm key={area.areaId} area={area} />
              ))}
              <AreaForm />
            </div>
          </section>
          <section className={styles.section}>
            <SectionHeading
              number="03"
              title="Resident directory"
              description="Add a record or review an assignment. Use synthetic information in this local demo."
            />
            <ResidentForm snapshot={snapshot} />
          </section>
          <section className={styles.section}>
            <SectionHeading
              number="04"
              title="Optional facility layout"
              description="A floor plan is a location aid. The room directory is enough to use the workspace."
            />
            <div className={styles.capabilityRows}>
              <div>
                <strong>Floor-plan files</strong>
                <p>
                  Private plan upload, room matching and versioned layout
                  associations are not connected. No blueprint is uploaded,
                  extracted or treated as a monitoring-coverage map here.
                </p>
              </div>
              <div>
                <strong>Available alternative</strong>
                <p>
                  Maintain care areas and room assignments in the resident
                  directory above. Monitoring and shared-station coverage do not
                  depend on a floor plan.
                </p>
              </div>
            </div>
          </section>
          <nav
            aria-label="Other administration"
            className={styles.relatedLinks}
          >
            <Link href="/station">
              Manage shared stations <span aria-hidden="true">↗</span>
            </Link>
            <Link href="/imports">
              Review a roster import <span aria-hidden="true">↗</span>
            </Link>
          </nav>
        </>
      ) : null}
    </AdminFrame>
  );
}
