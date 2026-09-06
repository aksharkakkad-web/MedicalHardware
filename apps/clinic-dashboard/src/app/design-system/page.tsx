import type { CSSProperties, ReactNode } from "react";

import { AlertIcon, ArrowIcon, CareMark, CheckIcon, DeviceIcon, EventIcon, MoreIcon, OverviewIcon, PanelRightIcon, ScenarioIcon, SearchIcon } from "../../components/icons/icons";
import { Button, IconButton } from "../../components/ui/button";
import { FormField, FormFieldset } from "../../components/ui/form-field";
import { ResidentRecords, type ResidentRecord } from "../../components/ui/resident-records";
import { StatusIndicator } from "../../components/ui/status-indicator";
import { SystemFeedback, SystemLifecycle, SystemStateCatalog } from "../../components/ui/system-state";
import { DesignSystemShell } from "./design-system-shell";
import { ExportActions } from "./export-actions";
import styles from "./page.module.css";

const sections = [
  ["01", "Foundation"],
  ["02", "Color"],
  ["03", "Typography"],
  ["04", "Space & shape"],
  ["05", "App shell"],
  ["06", "Iconography"],
  ["07", "Actions"],
  ["08", "Forms"],
  ["09", "Status"],
  ["10", "Data"],
  ["11", "Care patterns"],
] as const;

const foundationColors = [
  ["Canvas white", "Page canvas", "App shell and primary workspace", "canvasToken", "#FFFFFF"],
  ["Surface white", "Working surface", "Primary content and controls", "paper0", "#FFFFFF"],
  ["Neutral 50", "Quiet surface", "Hover and grouped secondary content", "paper50", "#FAFAFA"],
  ["Neutral 100", "Alternate surface", "Nested panels and muted sections", "paper100", "#F5F5F5"],
  ["Neutral 200", "Hairline", "Rows, controls, and surface edges", "paper200", "#E5E5E5"],
  ["Neutral 500", "Secondary text", "Helper copy and metadata", "ink600", "#737373"],
  ["Neutral 900", "Primary text", "Headings and decisions", "ink950", "#171717"],
] as const;

const brandColors = [
  ["Blue 50", "Selection wash", "Selected rows and active navigation", "cobalt50", "#EFF6FF"],
  ["Blue 100", "Strong selection", "Focused information groups", "cobalt100", "#DBEAFE"],
  ["Blue 600", "Brand and interaction", "Primary actions and focus", "cobalt600", "#2563EB"],
  ["Blue 800", "Pressed interaction", "Pressed primary actions", "cobalt800", "#1E40AF"],
  ["Neutral 600", "Device information", "Device and data context", "sky400", "#525252"],
  ["Electric blue", "Brand accent only", "Brand moments, never severity", "violet500", "#2563EB"],
  ["Green 700", "Positive accent", "Healthy and available states", "mint400", "#15803D"],
] as const;

const statusColors = [
  ["Positive green", "Operationally positive", "Healthy, online, or current confirmation", "positive", "#15803D"],
  ["Watch amber", "Review support", "Watch, limited, or delayed states", "watch", "#A16207"],
  ["Risk red", "Resident attention", "Critical or high attention priority", "risk", "#B42318"],
  ["Unavailable gray", "Evidence limitation", "Missing, stale, or unavailable evidence", "unavailable", "#737373"],
] as const;

const spacing = [
  ["04", "4px"],
  ["08", "8px"],
  ["12", "12px"],
  ["16", "16px"],
  ["24", "24px"],
  ["32", "32px"],
  ["48", "48px"],
  ["64", "64px"],
] as const;

const radii = [
  ["Tiny detail", "4px", "radiusSquare"],
  ["Input", "6px", "radiusField"],
  ["Button", "8px", "radiusControl"],
  ["Card", "12px", "radiusSurface"],
  ["Floating", "12px", "radiusFloating"],
] as const;

const residentRecords: ResidentRecord[] = [
  {
    id: "avery-chen",
    residentName: "Avery Chen",
    room: "Room 214",
    attentionReason: "No attention priority; monitoring is current",
    attention: "none",
    monitoring: "active",
    confidence: "high",
    freshness: { value: "current" },
    device: "healthy",
    workflow: "acknowledged",
    primaryAction: { label: "Review record", href: "#section-11" },
    deviceDetails: "Radar, thermal, and Wi-Fi CSI sources are reporting.",
    lastObserved: "22 seconds ago",
  },
  {
    id: "jordan-lee",
    interaction: "hover",
    residentName: "Jordan Lee",
    room: "Room 108",
    attentionReason: "No attention priority; a current reading is available",
    attention: "none",
    monitoring: "active",
    confidence: "high",
    freshness: { value: "current" },
    device: "healthy",
    workflow: "acknowledged",
    primaryAction: { label: "Open record", href: "#section-11" },
    deviceDetails: "All three room sources are reporting.",
    lastObserved: "38 seconds ago",
  },
  {
    id: "sam-rivera",
    interaction: "selected",
    residentName: "Sam Rivera",
    room: "Room 302",
    attentionReason: "Multiple people may be present in the room",
    attention: "none",
    monitoring: "possible_multi_person",
    confidence: "unavailable",
    freshness: { value: "unknown" },
    device: "healthy",
    workflow: "new",
    primaryAction: { label: "Review record", href: "#section-11" },
    deviceDetails: "Room sources are reporting, but resident attribution is unavailable.",
    lastObserved: "Last current update unknown",
  },
  {
    id: "priya-shah",
    residentName: "Priya Shah",
    room: "Room 220",
    attentionReason: "Resident-away period needs a coverage check",
    attention: "watch",
    monitoring: "away",
    confidence: "unavailable",
    freshness: { value: "stale", lastCurrentUpdate: "08:38:12" },
    device: "healthy",
    workflow: "acknowledged",
    primaryAction: { label: "Review record", href: "#section-11" },
    deviceDetails: "All three room sources are reporting.",
    lastObserved: "4 minutes ago",
  },
  {
    id: "mateo-brooks",
    residentName: "Mateo Brooks",
    room: "Room 305",
    attentionReason: "Unexpected movement needs review",
    attention: "critical",
    monitoring: "active",
    confidence: "low",
    freshness: { value: "delayed" },
    device: "degraded",
    workflow: "investigating",
    primaryAction: { label: "Review record", href: "#section-11" },
    deviceDetails: "Radar and thermal are reporting; Wi-Fi CSI is delayed.",
    lastObserved: "1 minute ago",
  },
];

function Section({
  number,
  title,
  intro,
  children,
}: Readonly<{
  number: string;
  title: string;
  intro: string;
  children: ReactNode;
}>) {
  return (
    <section className={styles.section} id={`section-${number}`} tabIndex={-1} aria-labelledby={`heading-${number}`}>
      <header className={styles.sectionHeader}>
        <p className={styles.sectionNumber}>{number}</p>
        <div>
          <h2 id={`heading-${number}`}>{title}</h2>
          <p>{intro}</p>
        </div>
      </header>
      <div className={styles.sectionBody}>{children}</div>
    </section>
  );
}

function SpecimenLabel({ children }: Readonly<{ children: ReactNode }>) {
  return <p className={styles.specimenLabel}>{children}</p>;
}

export default function DesignSystemPage() {
  return (
    <DesignSystemShell>
      <a className={styles.skipLink} href="#design-system-content">Skip to specimens</a>
      <div className={styles.canvas}>
        <header className={styles.masthead}>
          <a className={styles.wordmark} href="#top" aria-label="Adaptive Care design system, back to top">
            <span aria-hidden="true">AC</span>
            <strong>Adaptive Care</strong>
          </a>
          <div className={styles.mastheadTools}>
            <p>ADAPTIVE CARE · CARE LEDGER V2</p>
            <ExportActions />
          </div>
        </header>

        <div className={styles.pageGrid} id="top">
          <aside className={styles.index} aria-label="Design system sections" data-design-system-index>
            <p className={styles.indexTitle}>Contents</p>
            <div className={styles.indexNavFrame}>
              <nav data-design-system-nav>
                <ol>
                  {sections.map(([number, label]) => (
                    <li key={number}>
                      <a href={`#section-${number}`}>
                        <span>{number}</span>
                        {label}
                      </a>
                    </li>
                  ))}
                </ol>
              </nav>
              <span className={styles.indexFade} data-design-system-nav-fade aria-hidden="true" hidden />
              <button className={styles.moreSections} type="button" data-design-system-more aria-label="More design system sections" hidden>
                <span>More sections</span>
                <ArrowIcon />
              </button>
            </div>
            <p className={styles.indexNote}>Quiet at rest.<br />Unmistakable when action is required.</p>
          </aside>

          <main className={styles.content} id="design-system-content" tabIndex={-1}>
            <section className={styles.hero} aria-labelledby="page-title">
              <p className={styles.eyebrow}>Visual language for contactless care operations</p>
              <h1 id="page-title">Calm enough to scan.<br /><em>Precise enough to trust.</em></h1>
              <div className={styles.heroSignal} aria-hidden="true"><span /><span /><span /><span /></div>
              <div className={styles.heroFoot}>
                <div className={styles.heroCopy}>
                  <p className={styles.heroCopyLabel}>Product rule</p>
                  <p>Adaptive Care separates resident attention, device health, confidence, freshness, and workflow so staff can decide what to do next.</p>
                  <p className={styles.heroTypeNote}>Product typography stays strong, compact, and readable across every operational screen.</p>
                </div>
                <dl>
                  <div><dt>Product mode</dt><dd>Clinic operations</dd></div>
                  <div><dt>Visual direction</dt><dd>Dub-derived neutral ledger</dd></div>
                  <div><dt>Interface density</dt><dd>Compact operational</dd></div>
                  <div><dt>Accessibility</dt><dd>WCAG 2.2 AA</dd></div>
                </dl>
              </div>
            </section>

            <Section number="01" title="Foundation" intro="A bright, approachable reference for live care operations.">
              <div className={styles.principles}>
                <article><span>01</span><h3>Separate the facts</h3><p>Risk, device health, confidence, freshness, and workflow are never collapsed into one status.</p></article>
                <article><span>02</span><h3>Show uncertainty</h3><p>Missing or limited evidence is labelled clearly. Last-known values never pretend to be current.</p></article>
                <article><span>03</span><h3>Lead with action</h3><p>One decision area gets one primary next step. Supporting detail stays useful and quiet.</p></article>
              </div>
              <blockquote className={styles.foundationQuote}>“Which resident needs my attention right now?”<footer>The question every clinic screen should answer within two seconds.</footer></blockquote>
            </Section>

            <Section number="02" title="Color" intro="Electric blue guides interaction. Operational color keeps its exact meaning.">
              <div className={styles.colorGroup}>
                <SpecimenLabel>Foundation tokens</SpecimenLabel>
                <div className={styles.swatchStrip}>
                  {foundationColors.map(([name, role, use, className, value]) => <div className={styles[className]} key={name}><strong>{name}</strong><span>{role}</span><small>{use}</small><code>{value}</code></div>)}
                </div>
              </div>
              <div className={styles.colorGroup}>
                <SpecimenLabel>Brand and supporting tokens</SpecimenLabel>
                <div className={styles.swatchStrip}>
                  {brandColors.map(([name, role, use, className, value]) => <div className={styles[className]} key={name}><strong>{name}</strong><span>{role}</span><small>{use}</small><code>{value}</code></div>)}
                </div>
              </div>
              <div className={styles.colorGroup}>
                <SpecimenLabel>Operational status tokens</SpecimenLabel>
                <div className={styles.semanticStrip}>
                  {statusColors.map(([name, role, use, className, value]) => <div className={styles[className]} key={name}><strong>{name}</strong><span>{role}</span><small>{use}</small><code>{value}</code></div>)}
                </div>
              </div>
              <p className={styles.ruleNote}><strong>Color rule</strong> Blue means brand or interaction. Green, amber, red, and gray carry operational status. Device or data trouble never borrows resident-risk red.</p>
            </Section>

            <Section number="03" title="Typography" intro="Compact, direct language built for repeated scanning.">
              <div className={styles.typeSpecimens}>
                <div><p>Display · 36 / 40 · 650</p><strong className={styles.displayType}>Care, without the noise.</strong></div>
                <div><p>Page title · 30 / 36 · 650</p><strong className={styles.pageTitleType}>Residents needing attention</strong></div>
                <div><p>Major heading · 22 / 28 · 650</p><strong className={styles.majorType}>Morning care review</strong></div>
                <div><p>Section heading · 18 / 24 · 650</p><strong className={styles.productSectionType}>Monitoring coverage</strong></div>
                <div><p>Record title · 15 / 21 · 600</p><strong className={styles.recordType}>Resident B · Room 214</strong></div>
                <div><p>Body · 14 / 20 · 400</p><span className={styles.bodyType}>Monitoring is active. Latest room evidence arrived 38 seconds ago.</span></div>
                <div><p>Body strong · 14 / 20 · 550</p><strong className={styles.bodyStrongType}>Review the current evidence before resolving.</strong></div>
                <div><p>Label · 13 / 18 · 550</p><span className={styles.labelType}>Workflow state</span></div>
                <div><p>Metadata · 12 / 17 · 450</p><span className={styles.metadataType}>Updated 08:42 · Synthetic record</span></div>
                <div><p>Overline · 11 / 16 · 650</p><span className={styles.overlineType}>Resident attention</span></div>
                <div><p>Mono reading · 12 / 17 · 500</p><span className={styles.metaType}>AC-R214-B&nbsp;&nbsp; 08:42:18&nbsp;&nbsp; +00:38</span></div>
              </div>
              <div className={styles.numericSpecimen}><span>Geist Mono · Operational readings</span><strong>08:42:18&nbsp;&nbsp; 12 MIN&nbsp;&nbsp; 04 / 06</strong><code>DEVICE AC-214-A<br />FRAME 00018472</code></div>
            </Section>

            <Section number="04" title="Space & shape" intro="A four-pixel grid and compact geometry make the interface precise without becoming cramped.">
              <div className={styles.spacingGrid}>
                {spacing.map(([label, value]) => <div key={label}><span className={styles.spacingBar} style={{ "--specimen-size": value } as CSSProperties} /><strong>{label}</strong><small>{value}</small></div>)}
              </div>
              <div className={styles.geometryGrid}>
                <div><SpecimenLabel>Corner radius</SpecimenLabel><div className={styles.radiusRow}>{radii.map(([label, value, className]) => <div key={label}><span className={styles[className]} /><strong>{label}</strong><small>{value}</small></div>)}</div></div>
                <div><SpecimenLabel>Depth</SpecimenLabel><div className={styles.depthRow}><div className={styles.borderSurface}>Base surface<span>Hairline border</span></div><div className={styles.overlaySurface}>Popover<span>Overlap shadow</span></div></div></div>
              </div>
              <div className={styles.layoutSpacing}>
                <article><strong>16–20px</strong><span>Standard surface padding</span><small>Use 12px in compact toolbars and rows.</small></article>
                <article><strong>8–12px</strong><span>Related item gap</span><small>Use 24–32px between major modules.</small></article>
                <article><strong>32px</strong><span>Desktop page gutter</span><small>Reduce to 16px below 768px.</small></article>
                <article><strong>24–32px</strong><span>Module rhythm</span><small>Precision, not empty space, creates quality.</small></article>
              </div>
            </Section>

            <Section number="05" title="App shell" intro="Navigation stays quiet while the working surface carries the operational hierarchy.">
              <div className={styles.shellSpecimen} aria-label="Adaptive Care clinic shell specimen">
                <aside className={styles.shellSidebar}>
                  <div className={styles.shellBrand}><CareMark /><strong>Adaptive Care</strong></div>
                  <button className={styles.facilityControl} type="button"><span>NC</span><span><strong>Northstar Clinic</strong><small>Care operations</small></span><ArrowIcon /></button>
                  <nav aria-label="Clinic shell specimen navigation">
                    <p>Workspace</p>
                    <a className={styles.shellActive} href="#section-05"><OverviewIcon />Overview</a>
                    <a href="#section-10"><EventIcon />Events</a>
                    <a href="#section-10"><DeviceIcon />Devices</a>
                    <a href="#section-09"><ScenarioIcon />Scenario lab</a>
                  </nav>
                  <div className={styles.shellAccount}><span>MC</span><div><strong>Maya Chen</strong><small>Care coordinator</small></div><MoreIcon /></div>
                </aside>
                <div className={styles.shellWorkspace}>
                  <header className={styles.shellTopbar}><span>Northstar Clinic / Residents</span><div><SearchIcon /><span>Search residents</span><kbd>⌘ K</kbd></div></header>
                  <div className={styles.shellPage}>
                    <header className={styles.shellPageHeader}>
                      <div><p>Care operations</p><h3>Residents</h3><span>5 monitored rooms · updated just now</span></div>
                      <div className={styles.shellToolbar}><button type="button">Filter</button><button type="button">Sort</button><button type="button">Add resident</button></div>
                    </header>
                    <div className={styles.shellWorkArea}>
                      <section className={styles.shellMainSurface} aria-label="Resident working surface">
                        <div className={styles.shellTableHead}><span>Resident</span><span>Attention</span><span>Monitoring</span><span>Updated</span><span /></div>
                        <a href="#section-10"><span><strong>Mateo Brooks</strong><small>Room 305</small></span><span><b className={styles.riskDot} />Critical<small>Unexpected movement</small></span><span>Active<small>Low confidence</small></span><time>9:23 PM</time><ArrowIcon /></a>
                        <a href="#section-10"><span><strong>Avery Chen</strong><small>Room 214</small></span><span>No priority<small>Monitoring current</small></span><span>Active</span><time>9:22 PM</time><ArrowIcon /></a>
                        <a href="#section-10"><span><strong>Sam Rivera</strong><small>Room 302</small></span><span>No priority<small>Attribution unavailable</small></span><span><b className={styles.watchDot} />Limited<small>Multi-person possible</small></span><time>Unknown</time><ArrowIcon /></a>
                      </section>
                      <aside className={styles.shellRail}>
                        <div><p>Selected resident</p><h4>Mateo Brooks</h4><span>Room 305</span></div>
                        <dl><div><dt>Attention</dt><dd>Critical</dd></div><div><dt>Evidence</dt><dd>Low confidence</dd></div><div><dt>Device</dt><dd>Degraded</dd></div></dl>
                        <button type="button">Review resident <ArrowIcon /></button>
                      </aside>
                    </div>
                  </div>
                </div>
              </div>
              <div className={styles.shellSpecs}>
                <div><strong>208px</strong><span>Sidebar</span><small>58px collapsed</small></div>
                <div><strong>56px</strong><span>Topbar</span><small>One quiet utility row</small></div>
                <div><strong>32px</strong><span>Page gutter</span><small>24px at tablet widths</small></div>
                <div><strong>320px</strong><span>Secondary rail</span><small>Moves into a sheet below 1100px</small></div>
                <div><strong>400px</strong><span>Detail sheet</span><small>6px radius, floating shadow</small></div>
                <div><strong>36px</strong><span>Navigation item</span><small>16px icon, restrained selection</small></div>
                <div><strong>40px</strong><span>Toolbar</span><small>Directly above working content</small></div>
                <div><strong>40px</strong><span>Tabs</span><small>Underline selection, never pill tabs</small></div>
                <div><strong>480px</strong><span>Dialog</span><small>Maximum default width, floating only</small></div>
              </div>
              <p className={styles.ruleNote}><strong>Responsive rule</strong> Collapse the sidebar to icons at 1100px, move the secondary rail into a right sheet, and replace the sidebar with compact primary navigation below 768px. Main work remains first in the reading order.</p>
            </Section>

            <Section number="06" title="Iconography" intro="One internal line-icon family supports navigation and actions without competing with the words.">
              <div className={styles.iconLibrary}>
                <div><OverviewIcon /><strong>Overview</strong><span>18px navigation</span></div>
                <div><EventIcon /><strong>Events</strong><span>18px navigation</span></div>
                <div><DeviceIcon /><strong>Devices</strong><span>18px navigation</span></div>
                <div><SearchIcon /><strong>Search</strong><span>16px control</span></div>
                <div><PanelRightIcon /><strong>Detail panel</strong><span>16px control</span></div>
                <div><MoreIcon /><strong>More</strong><span>16px control</span></div>
                <div><CheckIcon /><strong>Complete</strong><span>20px important status</span></div>
                <div><AlertIcon /><strong>Attention</strong><span>20px important status</span></div>
              </div>
              <div className={styles.iconRules}><p><strong>Stroke</strong><span>1.8px, round caps and joins, currentColor.</span></p><p><strong>Default</strong><span>16px controls, 18px navigation, 20px only for important status or action.</span></p><p><strong>Do not use</strong><span>When the label is already clear, for decoration, or as the only carrier of status meaning.</span></p></div>
            </Section>

            <Section number="07" title="Actions" intro="Controls are restrained, stable, and explicit about outcome.">
              <div className={styles.controlStage}>
                <SpecimenLabel>Button hierarchy</SpecimenLabel>
                <div className={styles.buttonRow}>
                  <Button variant="primary">Review resident</Button>
                  <Button variant="secondary">Acknowledge</Button>
                  <Button variant="quiet">View history</Button>
                  <Button variant="danger">Remove device</Button>
                  <IconButton aria-label="More actions"><MoreIcon /></IconButton>
                </div>
                <SpecimenLabel>Loading and success specimens</SpecimenLabel>
                <div className={styles.buttonRow}>
                  <Button pending pendingLabel="Saving change">Saving change</Button>
                  <span className={styles.successButton}><CheckIcon />Saved</span>
                  <Button disabled>Resolve event</Button>
                </div>
                <SpecimenLabel>Primary action states</SpecimenLabel>
                <div className={styles.actionStates}>
                  <div><span>Resting</span><Button>Review resident</Button></div>
                  <div><span>Hover visual specimen</span><Button className={styles.simulatedHover}>Review resident</Button></div>
                  <div><span>Focus visual specimen</span><Button className={styles.simulatedFocus}>Review resident</Button></div>
                  <div><span>Disabled</span><Button disabled>Review resident</Button></div>
                </div>
                <SpecimenLabel>Icon action states</SpecimenLabel>
                <div className={styles.iconStates}>
                  <div><span>Resting</span><IconButton aria-label="More actions, resting"><MoreIcon /></IconButton></div>
                  <div><span>Hover visual specimen</span><IconButton className={styles.simulatedIconHover} aria-label="More actions, hover"><MoreIcon /></IconButton></div>
                  <div><span>Focus visual specimen</span><IconButton className={styles.simulatedFocus} aria-label="More actions, focus"><MoreIcon /></IconButton></div>
                  <div><span>Disabled</span><IconButton aria-label="More actions, disabled" disabled><MoreIcon /></IconButton></div>
                </div>
              </div>
              <p className={styles.ruleNote}><strong>Action rule</strong> Disabled actions keep their label and explain the reason nearby. Loading never changes a button’s width.</p>
            </Section>

            <Section number="08" title="Forms" intro="Visible labels, fixed control heights, and local recovery make forms boring in the best way.">
              <form className={styles.formStage}>
                <FormField id="resident-search" label="Search residents" hint="Search by resident label or room." type="search" placeholder="Example: Room 214" />
                <FormField id="room-search-focus" className={styles.focusField} label="Search focus state" hint="Visible focus uses the blue interaction ring." defaultValue="Room 214" />
                <FormField id="workflow-state" label="Workflow state" as="select" defaultValue="acknowledged" options={[{ value: "new", label: "New" }, { value: "acknowledged", label: "Acknowledged" }, { value: "investigating", label: "Investigating" }, { value: "resolved", label: "Resolved" }]} />
                <FormField id="room-disabled" label="Assigned room" hint="Room assignment is managed by an administrator." defaultValue="Room 214" disabled />
                <FormFieldset legend="Follow-up timing">
                  <label><input type="radio" name="follow-up" defaultChecked /> This round</label>
                  <label><input type="radio" name="follow-up" /> Next round</label>
                </FormFieldset>
                <label className={styles.checkbox}><input type="checkbox" defaultChecked /><span>Record staff observation pending review</span></label>
                <FormField id="care-note" label="Care note · error state" hint="Required fields stay neutral until validation fails." error="Add what staff observed before saving." as="textarea" required />
                <Button>Save observation</Button>
              </form>
            </Section>

            <Section number="09" title="Status" intro="Six independent axes describe what is known, what is limited, and what staff should do next.">
              <p className={styles.ruleNote}><strong>Status rule</strong> Attention, monitoring, confidence, freshness, device, and workflow are separate facts. Their colors support the written meaning; they never replace it.</p>
              <div className={styles.statusAxisCatalog}>
                <article className={styles.statusAxisCard}>
                  <div className={styles.statusAxisHeader}><h3>Attention</h3><p>Resident-facing priority and caregiver urgency.</p></div>
                  <div className={styles.statusAxisValues}>
                    <StatusIndicator axis="attention" value="critical" />
                    <StatusIndicator axis="attention" value="high" />
                    <StatusIndicator axis="attention" value="watch" />
                    <StatusIndicator axis="attention" value="none" />
                  </div>
                </article>
                <article className={styles.statusAxisCard}>
                  <div className={styles.statusAxisHeader}><h3>Monitoring</h3><p>Whether resident attribution is usable.</p></div>
                  <div className={styles.statusAxisValues}>
                    <StatusIndicator axis="monitoring" value="active" />
                    <StatusIndicator axis="monitoring" value="away" />
                    <StatusIndicator axis="monitoring" value="possible_multi_person" />
                    <StatusIndicator axis="monitoring" value="paused" />
                    <StatusIndicator axis="monitoring" value="calibrating" />
                    <StatusIndicator axis="monitoring" value="unavailable" />
                  </div>
                </article>
                <article className={styles.statusAxisCard}>
                  <div className={styles.statusAxisHeader}><h3>Confidence</h3><p>Evidence quality and attribution certainty.</p></div>
                  <div className={styles.statusAxisValues}>
                    <StatusIndicator axis="confidence" value="high" />
                    <StatusIndicator axis="confidence" value="medium" />
                    <StatusIndicator axis="confidence" value="low" />
                    <StatusIndicator axis="confidence" value="unavailable" />
                  </div>
                </article>
                <article className={styles.statusAxisCard}>
                  <div className={styles.statusAxisHeader}><h3>Freshness</h3><p>When evidence was last current; last-known values are not live.</p></div>
                  <div className={styles.statusAxisValues}>
                    <StatusIndicator axis="freshness" value="current" />
                    <StatusIndicator axis="freshness" value="delayed" />
                    <StatusIndicator axis="freshness" value="stale" lastCurrentUpdate="08:42:18" />
                    <StatusIndicator axis="freshness" value="unknown" />
                  </div>
                </article>
                <article className={styles.statusAxisCard}>
                  <div className={styles.statusAxisHeader}><h3>Device</h3><p>Room-unit and source health, not resident status.</p></div>
                  <div className={styles.statusAxisValues}>
                    <StatusIndicator axis="device" value="healthy" />
                    <StatusIndicator axis="device" value="degraded" />
                    <StatusIndicator axis="device" value="offline" />
                    <StatusIndicator axis="device" value="maintenance" />
                  </div>
                </article>
                <article className={styles.statusAxisCard}>
                  <div className={styles.statusAxisHeader}><h3>Workflow</h3><p>Work lifecycle; resolved history remains immutable.</p></div>
                  <div className={styles.statusAxisValues}>
                    <StatusIndicator axis="workflow" value="new" />
                    <StatusIndicator axis="workflow" value="acknowledged" />
                    <StatusIndicator axis="workflow" value="investigating" />
                    <StatusIndicator axis="workflow" value="resolved" />
                  </div>
                </article>
              </div>
              <div className={styles.statusContext}>
                <div><SpecimenLabel>Contextual display</SpecimenLabel><p>Show the status that changes the decision in this view. Do not render all six axes just because the data exists.</p></div>
                <table aria-label="Contextual status display">
                  <thead><tr><th scope="col">View</th><th scope="col">Default</th><th scope="col">Show only when it changes interpretation</th></tr></thead>
                  <tbody>
                    <tr><th scope="row">Dashboard queue</th><td>Attention + reason</td><td>Monitoring, confidence, or freshness when limited or unavailable</td></tr>
                    <tr><th scope="row">Event detail</th><td>Attention, workflow, evidence quality</td><td>Monitoring when attribution is affected; device as secondary context</td></tr>
                    <tr><th scope="row">Resident detail</th><td>Attention, monitoring, relevant evidence</td><td>Freshness, device, and workflow when they explain the current state</td></tr>
                    <tr><th scope="row">Device views</th><td>Device health + freshness</td><td>Monitoring when source state limits resident attribution</td></tr>
                  </tbody>
                </table>
              </div>
              <div className={styles.statusComposite}>
                <div className={styles.statusCompositeHeader}><div><SpecimenLabel>Composite example · synthetic/test-only</SpecimenLabel><h3>Independent facts can coexist</h3></div><span className={styles.statusCompositeCode}>NO SINGLE SCORE</span></div>
                <div className={styles.statusCompositeValues}>
                  <StatusIndicator axis="attention" value="high" />
                  <StatusIndicator axis="monitoring" value="active" />
                  <StatusIndicator axis="confidence" value="low" />
                  <StatusIndicator axis="freshness" value="stale" lastCurrentUpdate="08:42:18" />
                  <StatusIndicator axis="device" value="offline" />
                  <StatusIndicator axis="workflow" value="investigating" />
                </div>
                <p className={styles.statusCompositeExplanation}><strong>Next action:</strong> Review the event and device connection. These statuses are separate facts; do not treat a stale, offline signal as resident-specific without current supporting evidence.</p>
              </div>
              <div className={styles.evidenceStack}>
                <div className={styles.evidenceStackHeader}><SpecimenLabel>Evidence truth stack · synthetic/test-only</SpecimenLabel><p>Each layer has a different source and responsibility.</p></div>
                <article><span>01 · Sensor evidence</span><h3>Observed input and data quality</h3><p>Synthetic/test-only example: room telemetry, source contact, and timestamps are observed inputs. They are not a medical conclusion.</p></article>
                <article><span>02 · Deterministic warning</span><h3>Rule-based warning</h3><p>Synthetic/test-only rule output stays visible and cannot be suppressed by AI. Staff review the evidence and policy context.</p></article>
                <article><span>03 · AI interpretation</span><h3>Possible interpretation</h3><p>Plain-language interpretation of structured evidence only; it is never a diagnosis and cannot invent facts.</p></article>
                <article><span>04 · Staff observation</span><h3>Human-entered context</h3><p>Record what staff observed or checked. This context supports workflow and does not rewrite immutable history.</p></article>
              </div>
            </Section>

            <Section number="10" title="Data" intro="A resident queue exposes only the facts needed to choose what to inspect next.">
              <SpecimenLabel>Resident records · synthetic/test-only</SpecimenLabel>
              <ResidentRecords records={residentRecords} />
              <p className={styles.ruleNote}><strong>Responsive rule</strong> Desktop uses a scannable table; narrow screens preserve the decision facts and move device and workflow detail into a native disclosure without horizontal panning.</p>
            </Section>

            <Section number="11" title="Care patterns" intro="Semantic specification stays rigorous; actual care UI stays concise and task-focused.">
              <SpecimenLabel>Operational manifestations · synthetic/test-only</SpecimenLabel>
              <div className={styles.careManifestations}>
                <article data-tone="risk"><div><span>Critical</span><strong>Unexpected movement</strong><p>Low-confidence evidence · updated 1 minute ago</p></div><a href="#section-10">Review resident <ArrowIcon /></a></article>
                <article data-tone="watch"><div><span>Watch</span><strong>Resident-away period</strong><p>Current room sources · attribution paused</p></div><a href="#section-10">Open record <ArrowIcon /></a></article>
                <article data-tone="neutral"><div><span>Unavailable</span><strong>Multiple people may be present</strong><p>Resident-specific attribution unavailable</p></div><a href="#section-10">View evidence <ArrowIcon /></a></article>
              </div>
              <div className={styles.operationalStates}>
                <SpecimenLabel>Semantic specification · synthetic/test-only</SpecimenLabel>
                <p className={styles.operationalStatesIntro}>The UI above shows the concise manifestation. The expandable specification below preserves what is known, limited, why it matters, and every allowed action for implementation and review.</p>
                <details className={styles.semanticDocs}>
                  <summary>Open complete care-state specification</summary>
                  <SystemStateCatalog />
                  <SystemLifecycle />
                  <SystemFeedback />
                </details>
              </div>
              <footer className={styles.pageFooter}><span>Adaptive Care · Care Ledger V2</span><a href="#top">Back to top <ArrowIcon /></a></footer>
            </Section>
          </main>
        </div>
      </div>
    </DesignSystemShell>
  );
}
