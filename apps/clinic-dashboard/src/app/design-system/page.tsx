import type { CSSProperties, ReactNode, SVGProps } from "react";

import { DesignSystemShell } from "./design-system-shell";
import styles from "./page.module.css";

const sections = [
  ["01", "Foundation"],
  ["02", "Color"],
  ["03", "Typography"],
  ["04", "Space & shape"],
  ["05", "Actions"],
  ["06", "Forms"],
  ["07", "Status"],
  ["08", "Data"],
  ["09", "Care patterns"],
] as const;

const foundationColors = [
  ["Canvas", "Page background", "App shell and section canvas", "canvasToken", "#FBFAF8"],
  ["White", "Working surface", "Cards, forms, and tables", "paper0", "#FFFFFF"],
  ["Mist 25", "Lifted surface", "Hover and quiet modules", "paper50", "#FBFCFF"],
  ["Mist 50", "Cool support", "Informational section canvas", "paper100", "#F4F7FC"],
  ["Mist 200", "Light border", "Card and table boundaries", "paper200", "#DDE4EF"],
  ["Ink 600", "Secondary text", "Helper copy and metadata", "ink600", "#536174"],
  ["Ink 950", "Primary text", "Headings and decisions", "ink950", "#111827"],
] as const;

const brandColors = [
  ["Blue 50", "Selection wash", "Selected rows and active navigation", "cobalt50", "#EEF4FF"],
  ["Blue 100", "Strong selection", "Focused information groups", "cobalt100", "#DCE9FF"],
  ["Blue 600", "Brand and interaction", "Primary actions and focus", "cobalt600", "#175CD3"],
  ["Blue 800", "Pressed interaction", "Pressed primary actions", "cobalt800", "#123E9A"],
  ["Sky 400", "Informational accent", "Device and data information", "sky400", "#55ACFF"],
  ["Violet 500", "Brand accent only", "Charts and brand moments, never severity", "violet500", "#7357D8"],
  ["Mint 400", "Positive accent", "Positive highlights, not the healthy status", "mint400", "#76D6B1"],
] as const;

const statusColors = [
  ["Healthy green", "Operational healthy", "Online and current monitoring", "positive", "#147D5A"],
  ["Warning amber", "Operational warning", "Limited coverage and review", "watch", "#A15C00"],
  ["Critical red", "Resident risk", "High and critical resident attention", "risk", "#C53B30"],
  ["Unavailable gray", "Operational unavailable", "Missing, stale, or unavailable data", "unavailable", "#526172"],
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
  ["Small", "4px", "radiusSquare"],
  ["Control", "8px", "radiusField"],
  ["Specimen", "20px", "radiusControl"],
  ["Feature", "24px", "radiusOverlay"],
] as const;

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
    <section className={styles.section} id={`section-${number}`} aria-labelledby={`heading-${number}`}>
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

function CheckIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true" {...props}>
      <path d="m5 10.4 3.1 3.1L15.4 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function AlertIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true" {...props}>
      <path d="M10 3.2 17 16H3L10 3.2Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M10 7.5v3.8M10 14.1v.1" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function SignalIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true" {...props}>
      <path d="M4 14.5v1.2M8 11v4.7M12 7.5v8.2M16 4v11.7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function MoreIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" {...props}>
      <circle cx="4" cy="10" r="1.5" /><circle cx="10" cy="10" r="1.5" /><circle cx="16" cy="10" r="1.5" />
    </svg>
  );
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
          <p>ADAPTIVE CARE · DESIGN SYSTEM V3.0</p>
        </header>

        <div className={styles.pageGrid} id="top">
          <aside className={styles.index} aria-label="Design system sections">
            <p className={styles.indexTitle}>Contents</p>
            <nav>
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
            <p className={styles.indexNote}>Quiet at rest.<br />Unmistakable when action is required.</p>
          </aside>

          <main className={styles.content} id="design-system-content">
            <section className={styles.hero} aria-labelledby="page-title">
              <p className={styles.eyebrow}>Visual language for contactless care operations</p>
              <h1 id="page-title">Calm enough to scan.<br /><em>Precise enough to trust.</em></h1>
              <div className={styles.heroSignal} aria-hidden="true"><span /><span /><span /><span /></div>
              <div className={styles.heroFoot}>
                <div className={styles.heroCopy}>
                  <p className={styles.heroCopyLabel}>Product rule</p>
                  <p>Adaptive Care separates resident attention, device health, confidence, freshness, and workflow so staff can decide what to do next.</p>
                  <p className={styles.heroTypeNote}>The brand can speak boldly here. Product UI typography stays compact and restrained.</p>
                </div>
                <dl>
                  <div><dt>Product mode</dt><dd>Clinic operations</dd></div>
                  <div><dt>Visual direction</dt><dd>Clear Signal V3.0</dd></div>
                  <div><dt>Product type</dt><dd>Restrained Geist Sans</dd></div>
                  <div><dt>Access floor</dt><dd>WCAG 2.2 AA</dd></div>
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

            <Section number="02" title="Color" intro="Cobalt guides action. Supporting color stays explicit and useful.">
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
              <p className={styles.ruleNote}><strong>Color rule</strong> Blue means brand or interaction. Sky means information. Violet is a brand accent and never severity. Green, amber, red, and gray carry operational status.</p>
            </Section>

            <Section number="03" title="Typography" intro="Compact, direct language built for repeated scanning.">
              <div className={styles.typeSpecimens}>
                <div><p>Display · 32 / 38 · 650</p><strong className={styles.displayType}>Care, without the noise.</strong></div>
                <div><p>Page title · 28 / 34 · 650</p><strong className={styles.pageTitleType}>Residents needing attention</strong></div>
                <div><p>Major heading · 22 / 28 · 650</p><strong className={styles.majorType}>Morning care review</strong></div>
                <div><p>Section heading · 18 / 24 · 650</p><strong className={styles.productSectionType}>Monitoring coverage</strong></div>
                <div><p>Record title · 15 / 21 · 600</p><strong className={styles.recordType}>Resident B · Room 214</strong></div>
                <div><p>Body · 14 / 20 · 400</p><span className={styles.bodyType}>Monitoring is active. Latest room evidence arrived 38 seconds ago.</span></div>
                <div><p>Body strong · 14 / 20 · 550</p><strong className={styles.bodyStrongType}>Review the current evidence before resolving.</strong></div>
                <div><p>Label · 13 / 18 · 550</p><span className={styles.labelType}>Assign care owner</span></div>
                <div><p>Metadata · 12 / 17 · 450</p><span className={styles.metadataType}>Updated 08:42 · Synthetic record</span></div>
                <div><p>Overline · 11 / 16 · 650</p><span className={styles.overlineType}>Resident attention</span></div>
                <div><p>Mono reading · 12 / 17 · 500</p><span className={styles.metaType}>AC-R214-B&nbsp;&nbsp; 08:42:18&nbsp;&nbsp; +00:38</span></div>
              </div>
              <div className={styles.numericSpecimen}><span>Geist Mono · Operational readings</span><strong>08:42:18&nbsp;&nbsp; 12 MIN&nbsp;&nbsp; 04 / 06</strong><code>DEVICE AC-214-A<br />FRAME 00018472</code></div>
            </Section>

            <Section number="04" title="Space & shape" intro="A four-pixel grid, open spacing, and soft geometry keep information approachable.">
              <div className={styles.spacingGrid}>
                {spacing.map(([label, value]) => <div key={label}><span className={styles.spacingBar} style={{ "--specimen-size": value } as CSSProperties} /><strong>{label}</strong><small>{value}</small></div>)}
              </div>
              <div className={styles.geometryGrid}>
                <div><SpecimenLabel>Corner radius</SpecimenLabel><div className={styles.radiusRow}>{radii.map(([label, value, className]) => <div key={label}><span className={styles[className]} /><strong>{label}</strong><small>{value}</small></div>)}</div></div>
                <div><SpecimenLabel>Depth</SpecimenLabel><div className={styles.depthRow}><div className={styles.borderSurface}>Base surface<span>Hairline border</span></div><div className={styles.overlaySurface}>Popover<span>Overlap shadow</span></div></div></div>
              </div>
              <div className={styles.layoutSpacing}>
                <article><strong>24px</strong><span>Default card padding</span><small>Use 16px on narrow screens.</small></article>
                <article><strong>16px</strong><span>Related component gap</span><small>Use 24px between major modules.</small></article>
                <article><strong>32px</strong><span>Desktop page gutter</span><small>Reduce to 16px below 768px.</small></article>
                <article><strong>96px</strong><span>Section spacing</span><small>Keep reference groups distinct.</small></article>
              </div>
            </Section>

            <Section number="05" title="Actions" intro="Controls are restrained, stable, and explicit about outcome.">
              <div className={styles.controlStage}>
                <SpecimenLabel>Button hierarchy</SpecimenLabel>
                <div className={styles.buttonRow}>
                  <button className={styles.primaryButton} type="button">Review resident</button>
                  <button className={styles.secondaryButton} type="button">Assign to me</button>
                  <button className={styles.ghostButton} type="button">View history</button>
                  <button className={styles.destructiveButton} type="button">Remove device</button>
                  <button className={styles.iconButton} type="button" aria-label="More actions"><MoreIcon /></button>
                </div>
                <div className={styles.buttonRow}>
                  <button className={styles.loadingButton} type="button" aria-busy="true"><span aria-hidden="true" />Saving change</button>
                  <button className={styles.successButton} type="button"><CheckIcon />Saved</button>
                  <button className={styles.primaryButton} type="button" disabled>Resolve event</button>
                </div>
                <SpecimenLabel>Primary action states</SpecimenLabel>
                <div className={styles.actionStates}>
                  <div><span>Resting</span><button className={styles.primaryButton} type="button">Review resident</button></div>
                  <div><span>Hover</span><button className={`${styles.primaryButton} ${styles.simulatedHover}`} type="button">Review resident</button></div>
                  <div><span>Focus</span><button className={`${styles.primaryButton} ${styles.simulatedFocus}`} type="button">Review resident</button></div>
                  <div><span>Disabled</span><button className={styles.primaryButton} type="button" disabled>Review resident</button></div>
                </div>
                <SpecimenLabel>Icon action states</SpecimenLabel>
                <div className={styles.iconStates}>
                  <div><span>Resting</span><button className={styles.iconButton} type="button" aria-label="More actions, resting"><MoreIcon /></button></div>
                  <div><span>Hover</span><button className={`${styles.iconButton} ${styles.simulatedIconHover}`} type="button" aria-label="More actions, hover"><MoreIcon /></button></div>
                  <div><span>Focus</span><button className={`${styles.iconButton} ${styles.simulatedFocus}`} type="button" aria-label="More actions, focus"><MoreIcon /></button></div>
                  <div><span>Disabled</span><button className={styles.iconButton} type="button" aria-label="More actions, disabled" disabled><MoreIcon /></button></div>
                </div>
              </div>
              <p className={styles.ruleNote}><strong>Action rule</strong> Disabled actions keep their label and explain the reason nearby. Loading never changes a button’s width.</p>
            </Section>

            <Section number="06" title="Forms" intro="Visible labels, clear requirements, and local recovery.">
              <form className={styles.formStage}>
                <div className={styles.fieldGroup}>
                  <label htmlFor="resident-search">Search residents</label>
                  <p id="resident-search-hint">Search by resident label or room.</p>
                  <input id="resident-search" type="search" aria-describedby="resident-search-hint" placeholder="Example: Room 214" />
                </div>
                <div className={`${styles.fieldGroup} ${styles.focusField}`}>
                  <label htmlFor="room-search-focus">Search focus state</label>
                  <p id="room-search-focus-hint">Visible focus uses the blue interaction ring.</p>
                  <input id="room-search-focus" aria-describedby="room-search-focus-hint" defaultValue="Room 214" />
                </div>
                <div className={styles.fieldGroup}>
                  <label htmlFor="owner">Assign care owner</label>
                  <select id="owner" defaultValue="maya"><option value="maya">Maya Chen</option><option value="jon">Jon Bell</option></select>
                </div>
                <fieldset className={styles.fieldset}>
                  <legend>Follow-up timing</legend>
                  <label><input type="radio" name="follow-up" defaultChecked /> This round</label>
                  <label><input type="radio" name="follow-up" /> Next round</label>
                </fieldset>
                <label className={styles.checkbox}><input type="checkbox" defaultChecked /><span>Notify the assigned staff member</span></label>
                <div className={`${styles.fieldGroup} ${styles.errorField}`}>
                  <label htmlFor="care-note">Care note <span>Required</span></label>
                  <textarea id="care-note" aria-invalid="true" aria-describedby="care-note-error" defaultValue="Resident checked." />
                  <p id="care-note-error">Add what staff observed before saving.</p>
                </div>
                <button className={styles.primaryButton} type="button">Save observation</button>
              </form>
            </Section>

            <Section number="07" title="Status" intro="Five independent axes describe what is actually known.">
              <div className={styles.operationalStates}>
                <article className={styles.healthyState}><CheckIcon /><div><strong>Healthy</strong><p>Monitoring is online and current.</p></div></article>
                <article className={styles.warningState}><span aria-hidden="true">!</span><div><strong>Warning</strong><p>Coverage is limited and needs review.</p></div></article>
                <article className={styles.criticalState}><AlertIcon /><div><strong>Critical</strong><p>Resident attention leads the hierarchy.</p></div></article>
                <article className={styles.unavailableState}><span aria-hidden="true">×</span><div><strong>Unavailable</strong><p>No current evidence can be shown.</p></div></article>
              </div>
              <p className={styles.ruleNote}><strong>Status rule</strong> Healthy, warning, critical, and unavailable are operational states. Resident risk, device health, confidence, freshness, and workflow remain separate facts.</p>
              <div className={styles.statusMatrix}>
                <div className={styles.statusHeading}><span>Axis</span><span>Example</span><span>Meaning</span></div>
                <div><strong>Resident risk</strong><span className={`${styles.statusTag} ${styles.riskTag}`}><AlertIcon /> High</span><p>Resident attention leads.</p></div>
                <div><strong>Monitoring</strong><span className={`${styles.statusTag} ${styles.watchTag}`}>◐ Limited</span><p>Coverage is reduced.</p></div>
                <div><strong>Data confidence</strong><span className={`${styles.statusTag} ${styles.deviceTag}`}>? Low</span><p>Occupancy is unclear.</p></div>
                <div><strong>Device health</strong><span className={`${styles.statusTag} ${styles.unavailableTag}`}><SignalIcon /> Offline</span><p>Room unit has no contact.</p></div>
                <div><strong>Workflow</strong><span className={`${styles.statusTag} ${styles.actionTag}`}>● Assigned</span><p>Maya Chen owns the check.</p></div>
              </div>
              <div className={styles.inlineMessages}>
                <p className={styles.positiveMessage}><CheckIcon /><span><strong>Monitoring active</strong>Current room evidence is available.</span></p>
                <p className={styles.deviceMessage}><SignalIcon /><span><strong>Evidence delayed</strong>Last contact was 4 minutes ago.</span></p>
                <p className={styles.unavailableMessage}><span aria-hidden="true">×</span><span><strong>Monitoring unavailable</strong>No current evidence can be shown.</span></p>
              </div>
            </Section>

            <Section number="08" title="Data" intro="Repeated records use tables. Missing values say what they mean.">
              <div className={styles.tableFrame}>
                <div className={styles.tableToolbar}><div><h3>Resident inventory</h3><p>5 synthetic state specimens</p></div><button className={styles.secondaryButton} type="button">Filter residents</button></div>
                <div className={styles.tableScroll}>
                  <table>
                    <caption>Example resident monitoring inventory</caption>
                    <thead><tr><th scope="col">Resident</th><th scope="col">Monitoring</th><th scope="col">Confidence</th><th scope="col">Freshness</th><th scope="col">Row state</th><th scope="col" aria-label="Action" /></tr></thead>
                    <tbody>
                      <tr className={styles.normalRow}><th scope="row"><strong>Resident A</strong><span>Room 102</span></th><td><span className={`${styles.miniStatus} ${styles.positiveMini}`}>Active</span></td><td>High</td><td className={styles.numeric}>22 sec ago</td><td><span className={styles.rowStateLabel}>Normal</span></td><td><button className={styles.textButton} type="button">Open</button></td></tr>
                      <tr className={styles.hoverRow}><th scope="row"><strong>Resident B</strong><span>Room 214</span></th><td><span className={`${styles.miniStatus} ${styles.positiveMini}`}>Active</span></td><td>High</td><td className={styles.numeric}>38 sec ago</td><td><span className={styles.rowStateLabel}>Hover</span></td><td><button className={styles.textButton} type="button">Open</button></td></tr>
                      <tr className={styles.selectedRow}><th scope="row"><strong>Resident C</strong><span>Room 220</span></th><td><span className={`${styles.miniStatus} ${styles.positiveMini}`}>Active</span></td><td>Medium</td><td className={styles.numeric}>51 sec ago</td><td><span className={styles.rowStateLabel}>Selected</span></td><td><button className={styles.textButton} type="button">Open</button></td></tr>
                      <tr className={styles.warningRow}><th scope="row"><strong>Resident D</strong><span>Room 108</span></th><td><span className={`${styles.miniStatus} ${styles.watchMini}`}>Limited</span></td><td>Low</td><td className={styles.numeric}>4 min ago</td><td><span className={styles.rowStateLabel}>Warning</span></td><td><button className={styles.textButton} type="button">Review</button></td></tr>
                      <tr className={styles.criticalRow}><th scope="row"><strong>Resident F</strong><span>Room 302</span></th><td><span className={`${styles.miniStatus} ${styles.riskMini}`}>Attention</span></td><td>Medium</td><td className={styles.numeric}>1 min ago</td><td><span className={styles.rowStateLabel}>Critical</span></td><td><button className={styles.textButton} type="button">Review</button></td></tr>
                    </tbody>
                  </table>
                </div>
              </div>
              <div className={styles.stateRow}><div><strong>No active events</strong><p>The queue is clear. Monitoring continues.</p></div><div><strong>No filtered results</strong><p>Try removing a filter.</p><button className={styles.textButton} type="button">Clear filters</button></div><div><strong>Couldn’t refresh</strong><p>Showing data from 08:38.</p><button className={styles.textButton} type="button">Retry</button></div></div>
            </Section>

            <Section number="09" title="Care patterns" intro="Operational components keep priority, truth, ownership, and action together.">
              <SpecimenLabel>Attention queue item</SpecimenLabel>
              <div className={styles.attentionFrame}>
                <div className={styles.attentionTop}><span className={`${styles.statusTag} ${styles.riskTag}`}><AlertIcon /> High resident risk</span><span className={styles.elapsed}>12 min open</span></div>
                <div className={styles.attentionIdentity}><div><p>Resident B</p><h3>Unexpected movement needs review</h3><span>Room 214 · Synthetic scenario</span></div><button className={styles.primaryButton} type="button">Review resident</button></div>
                <div className={styles.truthGrid}>
                  <dl><dt>Confidence</dt><dd><strong>Low</strong><span>Occupancy is unclear</span></dd></dl>
                  <dl><dt>Freshness</dt><dd><strong>Current</strong><span>38 seconds ago</span></dd></dl>
                  <dl><dt>Device</dt><dd><strong>Online</strong><span>3 sources reporting</span></dd></dl>
                  <dl><dt>Workflow</dt><dd><strong>Assigned</strong><span>Maya Chen</span></dd></dl>
                </div>
              </div>
              <div className={styles.evidenceGrid}>
                <article><span>Resident status</span><h3>Monitoring active</h3><p>High confidence. Latest evidence arrived 38 seconds ago.</p><small>Keep risk, confidence, and freshness separate.</small></article>
                <article><span>Device status</span><h3>Room unit online</h3><p>Radar, thermal, and Wi-Fi sources are reporting.</p><small>Device health uses information or operational status, never resident-risk red.</small></article>
                <article><span>Alert hierarchy</span><ol className={styles.alertHierarchy}><li><b>1</b> Critical resident risk</li><li><b>2</b> Warning or overdue work</li><li><b>3</b> Device and data limits</li></ol><small>This synthetic example does not identify a medical cause.</small></article>
              </div>
              <footer className={styles.pageFooter}><span>Adaptive Care · Clear Signal V3.0</span><a href="#top">Back to top ↑</a></footer>
            </Section>
          </main>
        </div>
      </div>
    </DesignSystemShell>
  );
}
