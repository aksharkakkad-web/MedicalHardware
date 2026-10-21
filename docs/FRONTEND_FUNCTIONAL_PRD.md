# SYREN Frontend Functional Requirements PRD

Proposed V1 requirements for the frontend teammate. October 21, 2026.

SYREN should help staff in assisted living, memory care, nursing facilities, and other staffed residential care settings understand which residents need attention, review trustworthy monitoring information, coordinate a response, and carry unfinished work into the next shift. The initial market focus is the Midwest United States, including facility residents receiving hospice.

These are functional requirements and acceptance conditions. Visual design, colors, typography, layouts, navigation, screen structure, component choices, and final interface wording belong to the frontend teammate. Earlier visual concepts are not part of this handoff. The earlier preference for an initial experience containing both action items and the assigned room population is retained as an information requirement, without prescribing their placement.

The companion [Backend Telemetry Processing and Frontend Delivery PRD](https://chatgpt.com/space/page_f6f78fdc51308191b88992565751c196) describes proposed server behavior. Frontend requirements that need new backend support must be agreed through the shared contract before implementation. This handoff does not assert that those services already exist.

# 1 Confirmed product decisions

Only administrators need personal SYREN accounts. Routine staff must be able to use an approved shared computer, laptop, phone, or tablet without creating or signing into a personal account.

Each approved shared client has an administrator-assigned facility and coverage area. Staff need access to that area's residents, rooms, monitoring information, notifications, and permitted response actions. Several approved clients may cover the same area and must converge on the same server state.

The initial staff experience must contain both actionable work and the residents and rooms within the client's assigned area. Staff must be able to distinguish concerns awaiting a response, concerns already being handled, follow-up work, and monitoring problems.

Resident checks use quick choices with an optional note. Staff should not have to write a narrative for every routine action. The selected choice must retain its actual meaning and cannot manufacture a completed check, verified identity, diagnosis, or resolution.

The first version is self-contained. It uses SYREN's own facility, resident, room, context, monitoring, response, and handover records. Connections to EHRs, nurse-call systems, staff messaging products, and other care platforms are deferred until a specific service is chosen. Ordinary operating-system and browser notification delivery remains a necessary platform dependency.

The frontend communicates with the SYREN backend. It contains no code for communicating with monitoring hardware, reading a sensor, acquiring measurements, configuring Wi-Fi, provisioning a physical monitoring unit, or processing vendor sensor formats.

# 2 People and responsibilities

Routine users include nursing assistants, caregivers, licensed nurses, charge staff, and temporary or agency staff. Their clinical responsibilities differ by facility. SYREN must present the assigned workflow without assuming that every person using a shared client is a licensed nurse or authorized to make clinical decisions.

Routine shared access permits viewing the authorized area, reviewing concerns and evidence, recording response intent and resident-check outcomes, leaving follow-up information, and providing monitoring feedback where the backend authorizes those actions. It does not automatically permit changing access rights, resident identity, room assignment, approved clinical context, monitoring policy, or alert routes.

Administrators manage the facility, other administrators, approved shared clients, coverage areas, room and resident records, imports, alert destinations, and permitted policies. Changes with clinical implications must follow the facility's authorized clinical approval process. Calling someone an administrator does not establish clinical competence.

A shared action is attributable to the approved client, facility, recorded time, and server action record. SYREN must not claim that an individual nurse performed it. An optional self-reported name, if later added, remains unverified and cannot become a clinical signature or stronger permission.

The frontend teammate owns presentation, usability, accessible interactions, and frontend implementation. Backend owners own authorization, assignments, monitoring interpretation, event transitions, imports, notification routing, and durable audit records. Changes affecting both sides require a shared contract and matching acceptance tests.

# 3 Information staff need

For the authorized area, staff need the current resident and room directory, room-to-resident assignment, monitoring availability, current supported measurements, measurement times, important limitations, active concerns, response progress, follow-ups, and meaningful recent changes.

A concern must provide the resident and room, what was observed, when it happened, the backend-assigned priority when one exists, whether evidence is current, whether anyone has recorded a response, and the next permitted staff action. Additional evidence, relevant context, and prior response history must remain available.

Staff must be able to find a known resident or room without inspecting every record. Any search, filter, or remembered preference remains inside the client's authorized scope. Narrowing a view must not make active authorized urgent work silently disappear.

An empty result, an unassigned room, a resident away from the room, and a failure to load data have different meanings. The frontend must preserve those distinctions. It must not represent a disconnected room as empty or an incomplete response as an absence of concerns.

Residents and rooms must remain discoverable when readings are unavailable, assignment needs review, or coverage is limited. Selecting a resident must lead to the current authorized record, including available measurements, changes over time, care context, events, responses, and relevant history. The teammate chooses the interaction and presentation.

# 4 Facility and shared access setup

The frontend must support creating a facility record, configuring its name and time zone, establishing authorized administrative access, defining care areas, and setting up staff coverage and escalation contacts. Routine staff coverage must not create a requirement for individual staff accounts.

Email-based administrator sign-in, verification, and recovery must be supported through the selected authentication system. Google sign-in and enterprise identity connections are not dependencies of this first release. The frontend must make failed verification, expired recovery, and loss of permission recoverable without exposing resident data.

An existing facility cannot be claimed merely by entering its name. Joining an existing organization requires an invitation or another backend-approved administrative process. Knowing a room number or resident name must not grant access.

An administrator must be able to approve a shared client, give it a recognizable name, select its permitted area and actions, confirm notification setup, and revoke it later. The client must remember its approved station role across ordinary app restarts while its grant remains valid. Administrator logout removes administrative authority while preserving approved routine use.

An administrator may assign one area or a deliberate combination of areas to a shared client. Coverage is an explicit permission, rather than an inference from physical location, Wi-Fi network, or the currently selected filter. Staff cannot expand the permission by changing a local setting.

If a shared laptop moves to another wing, it retains its existing authorized area until an administrator changes it. The current area must be understandable so that staff can recognize the mismatch. A new browser profile, cleared browser storage, or a replacement device may require approval again.

Expired, revoked, and unapproved clients must have clear recovery guidance. On learning of revocation or reduced scope, a reachable client must remove information it is no longer permitted to display and stop submitting actions under the old grant. A backend cannot erase information from a powered-off screen or a previously captured copy.

Approved phone and tablet use must not depend on a staff member's personal email, personal Apple or Google account being registered with SYREN, or personal telephone number. Normal operating-system requirements for the selected device still apply.

# 5 Room and resident records

Administrators must be able to maintain areas and rooms, add residents, edit administrative details, mark admission and departure dates, record temporary absence, and assign a resident to a room with an effective time.

Stable backend identities link records. Room numbers are location labels and may be reused. A returning resident, a transfer, or two residents with similar names must not silently become the same record.

V1 permits one assigned resident per monitored room. A room directory containing a roommate arrangement must be retained for review, but the frontend cannot imply that SYREN can identify which person produced a reading. Resident-specific readings remain limited or unavailable when the backend cannot attribute them.

A room transfer must show the affected resident, old and new room, effective time, and any conflict requiring review. The backend must confirm the change before it is represented as saved. Historical observations stay attached to their original resident, room assignment, and time rather than being relabeled with the current occupant.

Unknown assignments and conflicting occupants must remain explicit. Staff must be able to flag an incorrect assignment through routine access. A report of an error does not itself grant permission to change identity or merge resident records.

Room monitoring-source associations are server-maintained records. Where authorized, the frontend may show or request a change to an association through the backend and report its confirmed result. No direct connection to a physical monitoring unit is part of this scope.

Departed residents must no longer appear as current occupants after the backend confirms the effective departure. Authorized historical records remain available under the retention and access policy. A late reading from a former assignment must not appear as the new resident's current measurement.

# 6 Private directory and medical document imports

The first release must support roster import from UTF-8 CSV and XLSX, alongside manual entry and correction. Spreadsheet files must be treated as data; executable content and macros are not an import mechanism. Administrators need a description of required fields, supported date formats, actual upload limits, and examples containing synthetic data.

Roster import must support room and area labels, a facility-specific resident identifier when available, resident name, assignment information, and effective dates. Optional fields must be clearly distinguishable from fields needed to confirm identity and assignment. The frontend must not demand an entire medical record to start monitoring.

Resident context may be entered manually or supplied as PDF documents. Text-based PDF extraction is required for the proposed document-import capability. Scanned PDFs may be stored privately for authorized review; automated extraction from scans is available only when the backend supports it. Otherwise the app must offer manual context entry and must not claim that the scan was extracted. Structured clinical exports can be brought in through supported data imports. A proprietary database backup or arbitrary database connection must not be advertised as automatically supported. Existing care-platform connectors are deferred.

Uploads need durable processing status, including received, processing, ready for review, rejected, failed, canceled, and applied where relevant. Closing the browser must not make a server import job disappear or require starting it again. The user must be able to return to its result.

Before an import changes active records, an authorized administrator must review what will be added or changed, unmatched people, duplicate candidates, ambiguous dates, missing identifiers, assignment conflicts, and extraction uncertainty. Re-uploading a file or retrying a request must not silently create duplicate residents or assignments.

Document extraction creates proposed facts with a source document, relevant passage or page where available, document date, extraction status, and review state. It does not automatically produce approved clinical truth. Conflicting or illegible material remains unresolved until reviewed; low-quality extraction must not be hidden by polished summary text.

A correction must preserve provenance and prior reviewed versions. Failed import must leave existing valid records intact. Any partial application must identify exactly which records changed and which did not, with a safe way to address remaining failures. An import must not erase unrelated records because they were absent from an uploaded file.

Raw documents and extracted medical context must remain private to their authorized facility and permitted users. They must not become publicly accessible URLs, appear in analytics, or be included in routine notification payloads. Routine shared views receive only the context allowed by their grant. Privileged source-document access remains separately authorized.

Supported file size, row count, processing limits, and specific extraction capabilities must come from the backend and be shown before submission. A feature awaiting backend support must be unavailable with an honest explanation and a supported manual alternative; a simulated success is not acceptable.

Uploaded files are untrusted source material. Their text must not instruct the application to change permissions, suppress events, run code, or bypass review. Extraction and summarization must follow authorized server policy and minimize identifying data sent to any approved processor.

# 7 Resident context and hospice

Staff need a concise, source-backed account of relevant resident background, usual routines, communication or assistance needs, reviewed care goals, and active follow-up information. Full medical histories should remain accessible only where appropriate to the person's role and the shared client's permission.

For each material contextual fact, the frontend must preserve source, date or effective interval, review status, and whether the information is current, disputed, or incomplete. A staff observation, extracted document statement, AI interpretation, and approved clinical plan have different authority.

Routine staff must be able to report a correction or a new observation. Those reports must not silently overwrite approved history or resident baselines. The system must show whether the report is saved and whether review is still needed.

For residents receiving hospice, staff need to identify the responsible care service, applicable contact route, reviewed comfort goals, and relevant facility instructions when supplied by an authorized source. SYREN must not assume that hospice status or a DNR label means all notifications should stop.

The frontend must not generate medication changes, treatment orders, diagnoses, or hospital-transfer instructions. Staff-facing next steps must come from the authorized backend workflow and care policy, with their limits preserved. An absent care plan remains unknown.

Temporary context, such as a resident being away or staff providing care, must include its actual scope and expiration where relevant. It must not indefinitely pause resident-specific interpretation through a forgotten toggle. Staff need to understand whether the report affected monitoring, reminders, baseline learning, or nothing yet; the backend makes that determination.

# 8 Measurements and monitoring information

The frontend must display only measurements the backend actually supplies and permits for the current resident and assignment. The contract must identify the measurement, value when available, unit, observation time, validity or quality, freshness, attribution eligibility, and reason for an unavailable result.

For example, pulse or breathing estimates may be shown when supplied as valid supported measurements. The frontend must not calculate an unsupported vital sign, infer a diagnosis from an observation, manufacture a precise value from a confidence band, or convert a missing value to zero.

A successful fetch now does not make an old reading current. Staff need to distinguish when the measurement was observed, when SYREN last synchronized, and whether the resident-specific interpretation is eligible. A historical value may be retained only with its actual time and explicit historical status.

Possible multi-person presence, uncertain assignment, and resident-away periods must preserve the backend's limits on resident attribution. The frontend must not choose a likely resident, attach another person's data to the room's assigned resident, or hide the reason values are unavailable.

Historical review must support useful time intervals and the backend's available resolution. It must preserve gaps, invalid periods, changes in setup or assignment, corrections, and missing coverage. Any aggregation must identify its meaning and interval. Averages and last-known values cannot masquerade as instantaneous current observations.

Staff need the available evidence relevant to a concern and meaningful comparisons supplied by the backend. The frontend must not independently decide whether a numerical deviation is clinically urgent, choose medical thresholds, or update the resident's baseline.

Monitoring availability, evidence confidence, measurement freshness, resident-facing priority, response state, and room monitoring health are distinct facts. The information presented must allow staff to understand combinations such as an open concern with unavailable new readings.

# 9 Concerns analysis and notifications

Actionable caregiver events, awareness or watch information, analysis pending, follow-up tasks, and operational monitoring failures must retain their distinct meanings. An analysis awaiting AI review is not automatically a high-priority caregiver event, and a missing AI result is not an all-clear.

For a caregiver event, the frontend needs its stable identity, affected resident and assignment, source evidence, onset and update times, current backend priority, status, response history, required follow-up, and permitted next actions. An interpretation must remain identifiable as an interpretation, with uncertainty and supporting evidence accessible.

The backend controls event creation, priority, reminders, escalation, and allowed state transitions. The frontend must preserve those decisions. A separately authorized urgent safety path may create provisional work; ordinary analysis failure must not cause the frontend to create its own critical concern.

Several measurements or notifications may refer to one event. The same event appearing in multiple contexts must not be counted as multiple separate emergencies. Distinct events concerning one resident must not be silently merged or hidden.

Opening a notification, viewing an event, or dismissing an operating-system notification must not mark a resident as checked or resolve the concern. Staff must be able to see whether a response has been recorded without opening every historical action.

Unresolved high or critical events must not silently disappear because a browser refreshes, a shift changes, a notification expires, or a room's newest reading is unavailable. Later notifications for a resolved event must lead to its current historical state.

Operational failures, including unavailable readings, failed delivery, lost coverage, and an expired temporary context report, must remain actionable without being mislabeled as evidence that a resident is deteriorating.

Notification urgency, repeat behavior, sound, and escalation timing follow an approved server policy and the supported delivery platform. The teammate must not hard-code medical urgency or independent reminder timers into the frontend.

# 10 Response and quick resident check choices

The required business sequence distinguishes accepting response responsibility, recording what happened during a resident check, and resolving or continuing follow-up. The final wording and interaction belong to the frontend teammate.

Recording response intent must immediately identify its server-confirmed source, such as an approved shared client, to other authorized clients. It indicates an intention reported from that client; it does not verify which person is going, prove arrival, or establish that care was delivered.

The frontend must preserve the meaning of existing backend actions. If an available endpoint records only acknowledgment, it cannot be relabeled as physical response or resident assessment. A stronger responsibility claim requires a matching documented backend command and audit event.

The quick-choice capability must represent at least these outcome meanings, without prescribing exact interface labels:

- Staff checked the resident and did not observe a concern at that time.
- Staff checked the resident and a concern remains.
- Staff checked the resident and requested further assistance.
- Staff could not complete a check.
- Staff believe the room, assignment, or monitoring information needs review.
- Another outcome needs a short explanation.

A choice that says the resident could not be checked must not create a completed-check record. Requesting assistance does not prove that assistance arrived. Reporting unreliable information does not automatically declare a false alarm or erase the event.

Notes are optional for the ordinary supported choices. An unusual outcome, a material exception, or a clinically required explanation may need a short additional detail under a documented facility policy. The app must explain the specific missing information instead of requiring a routine narrative for every check.

Staff need to record the actual check time when it differs from submission time. The record must preserve both and make clear that an entered historical time is staff-reported. Backdating cannot overwrite earlier actions or pretend that an overdue response happened on time.

A resident check and event closure are separate business results. A submission may request closure when permitted, but the app must make that consequence understandable and use the backend's confirmed result. A check alone must not silently close high-priority work.

Closure requires a meaningful supported outcome and any required follow-up disposition. Unresolved concern, inability to check, or assistance still pending must remain visible. The backend enforces allowed closure and any escalation or approval requirement.

Feedback about a misleading concern must be kept distinct from the response history. Staff should not have to submit the same description twice when one authorized action can safely reuse it, but partial saves must be reported accurately. Feedback must not promise immediate retraining or deletion of contradictory evidence.

# 11 Coordination across shared devices

Two clients covering the same resident must see the same event and confirmed workflow history. A response recorded from one approved shared phone must be visible from the station computer and any other authorized client.

The backend must arbitrate simultaneous actions. The frontend must handle the case where another client accepted responsibility, changed an event, or resolved it before the current submission. It must explain the current result and avoid overwriting newer work.

Network retries must not create duplicate checks, notes, or closures. A timeout means the result may be unknown; the frontend must reconcile the server record before asserting that an action failed or inviting a duplicate submission.

Staff need to release or hand over response responsibility when the backend supports that transition. The handover must not delete the original intent, pretend the resident was checked, reset elapsed time, or leave the next team unaware of an unresolved concern.

A shared phone may change hands between shifts without a personal login exchange. The client's approved identity and area remain clear. A transfer of the device does not prove that its new holder has accepted every open task.

A resident can be covered by overlapping areas or several approved clients. The app must preserve the backend's routing and responsibility rules rather than notifying every device indefinitely or treating the number of open devices as proof of staff coverage.

Routine context changes and ordinary app restarts must preserve confirmed work. A local unsaved draft must not be attached to another resident after switching records. Client-specific preferences must not alter facility-wide clinical policy.

# 12 Follow up and shift handover

Staff need to record that an event requires follow-up, what remains to be done, the responsible team or approved destination when known, and the due time when the backend requires one. Unknown responsibility must remain visible rather than being filled with an invented person.

Follow-up must survive app closure, staff change, shift change, and temporary network loss after a confirmed save. A concern awaiting review or assistance must not be archived merely because its first notification was acknowledged.

The handover capability must identify unresolved concerns, pending checks, due or overdue follow-ups, significant recent changes, relevant room transfers or context changes, analysis still pending, monitoring gaps, and notification or coverage failures for the authorized area and chosen interval.

Handover counts and source items must be consistent. Any generated summary must be grounded in the underlying records and preserve uncertainty. Staff must be able to inspect the records supporting a material statement.

A selected interval must be clear, including its time zone. The app must distinguish a quiet period with complete available monitoring from a period with missing or limited observation. A shift boundary cannot reset event age or resolve work.

Staff need a practical way to record that follow-up was completed or handed over. That action must not imply that an individual signed a clinical record unless identity was separately verified.

Handover supports staff communication and existing facility procedures. It must not require everyone to sign in individually or create an additional mandatory narrative whenever the same facts already exist in SYREN.

# 13 Shared phones laptops and background alerts

The functional scope includes approved shared phones, supported tablets, laptops, and station computers. The same authorized resident and event information must be usable on each supported class, with the same action meanings and authoritative state.

The product needs an explicit supported device, operating-system, browser, and app-mode list before release. “Any device” is not a testable delivery promise. A successful desktop notification test does not establish mobile, locked-screen, or sleeping-laptop behavior.

The web application may be installed as a PWA, meaning an installable web application, where the supported platform requires or benefits from it. Ordinary viewing and background notification eligibility may have different prerequisites.

For iPhone and iPad web push, the supported setup includes a Home Screen web app and user-granted notification permission. Setup must explain the actual required action in plain language and verify receipt on the intended shared device. [Apple WebKit documentation](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/)

Web push can deliver messages when an application page is not loaded, using browser and platform push infrastructure. This is a capability with platform conditions, rather than a guarantee that a powered-off, disconnected, silenced, or unsupported device will notify staff. [MDN Push API](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)

The backend must continue monitoring, storing events, and running the approved alert policy without a personal staff login and without an open monitoring page. Notification processing cannot live only in an active browser timer.

A facility must have at least one validated independent notification path for unattended operation. The route must be demonstrated with ordinary pages closed and all administrators logged out, using the actual supported platform state. Where web push cannot meet that test, another approved path is a launch dependency.

The app must distinguish configured, permission granted, test sent, test actually received, unavailable, and failed where these can be established. Notification permission or an accepted send request alone is not proof that a person heard or read an alert.

Lock-screen and operating-system notification content must be minimal by default and avoid resident names, diagnoses, document extracts, and unnecessary clinical details. Opening a notification must recheck current client authorization before showing resident information.

If permission is denied, an enrollment expires, or a client is revoked, the administrator must be able to recognize the loss and recover. The app must not repeatedly demand personal staff registration as the solution.

Administrators must be able to manage primary and backup shared destinations, confirm covered areas, run clearly labeled test notifications, and identify a route with no eligible recipient. SYREN must not imply that every OS suppression setting or delivery failure is remotely detectable.

Self-contained V1 excludes care-platform connectors. It still depends on hosting, authentication, and the relevant browser or operating-system push services. SMS, voice, or a named third-party delivery vendor requires a separate choice if needed to satisfy the independent-delivery requirement.

# 14 Optional facility layouts

A facility must be usable with a room directory alone. Uploading a floor plan or blueprint is optional and cannot become a prerequisite for resident monitoring, alert routing, or response.

When a facility supplies a plan, an authorized administrator must be able to associate its room labels with existing server room identities and review unmatched or duplicate labels. Automated extraction, where supported, remains a proposal until confirmed.

Room information on an uploaded plan must follow the same access scope as the directory. A plan must not expose other facilities, unauthorized wings, or resident details merely because the file contains them.

A changed plan, renamed room, or added wing must be versioned and reconciled with current room records. Existing history and assignments must not be detached or silently remapped.

Layouts are a location aid. They do not establish measurement coverage, observation through walls, precise person location, or an evacuation instruction. The teammate decides whether and how to present the capability, without a prescribed map design.

# 15 Administrative controls and operational readiness

Administrators need to maintain facility details, time zone, areas, rooms, residents, approved shared clients, permissions, imports, reviewed context, notification destinations, and the policies that their role is permitted to change.

The administrator must be able to determine which areas have valid resident assignments, available monitoring, approved shared access, and tested notification coverage. These are different readiness conditions. A functioning browser cannot by itself establish all of them.

Administrative changes must identify their scope and effective result. A change to one shared client's preference must not silently modify every client. A facility-wide alert policy change requires appropriate authorization and audit history.

Changes to notification routing, shared-client access, resident identity, assignment, and approved context must have understandable confirmation and backend validation appropriate to their consequence. Routine care actions should not inherit administrative setup complexity.

Administrators need a way to rename or revoke a lost shared phone, approve a replacement, update its area, and verify that future access and notifications follow the new authorization. Revoking a destination does not resolve the resident events it previously received.

A route without an eligible primary or backup must remain visible as an operational problem. A missing integration is not such a problem in V1 because care-platform integrations are deferred; a required notification path that has never been tested is.

The app must support an explicit test or demonstration context with synthetic records and labeled test notifications. Test events must not be sent to real care-response destinations accidentally or mix into live resident history.

# 16 Saving connectivity and recovery

Every mutation must provide a clear distinction between local entry, submission in progress, server-confirmed save, rejected input, unknown result, and failure. A pending or failed action must not look complete.

The frontend must distinguish loss of its server connection from a room's monitoring problem. A connected app can show stale measurements; a reconnecting app can have previously valid resident information. Those conditions must not be collapsed into one unexplained status.

The default is not to retain medical records persistently in browser caches or app storage. In-memory information may remain during a brief connection interruption with its actual age and limitations, subject to the grant and backend policy. App assets and notification enrollment must be handled separately from resident content.

An offline note or action is unsent until the server accepts it. The first version must not silently queue and later apply clinical workflow transitions in the background. If a draft is retained temporarily, staff must understand that another team member has not received it, and submission after reconnection must reconcile the current resident, event, and permission.

Server updates must recover from interruptions without losing changes between initial load and the live subscription. The frontend must reconcile versions, ignore obsolete duplicates, obtain a fresh snapshot when required, and clear data invalidated by authorization or assignment changes.

A retry must reuse the relevant action identity where supported so that one intended response produces at most one durable action. A server timeout followed by a confirmed successful action must not be presented as a second outstanding task.

When several requests have different outcomes, the app must report those outcomes separately. Saving a check successfully while feedback fails must not become “nothing saved” or “everything saved.”

Unexpected updates must not discard a resident-check draft, switch its target resident, or move input focus without warning. Restoring a connection cannot silently substitute demonstration values.

Errors should explain what staff can do next without exposing stack traces, database details, provider secrets, or raw monitoring payloads. When an action cannot safely continue, the app must preserve useful context and identify the facility's configured escalation or downtime route.

# 17 Frontend and backend responsibilities

The frontend consumes authorized product records from SYREN's documented backend interface. It must not connect directly to a database, read monitoring hardware, interpret vendor packets, or place credentials for server integrations in a browser bundle.

The backend must supply the meaning needed to render records correctly: stable identities, facility and area scope, effective assignment, resource version, source and observation times, units, quality and availability, event identity and disposition, permitted actions, confirmed action receipts, pagination, synchronization status, and operational failures.

The frontend must not fill missing contract fields with invented facts. A missing required field is an integration or data-quality problem to handle explicitly; a documented nullable field keeps its documented unknown or unavailable meaning.

Event action availability must come from authorization and current state, not only from hidden interface controls. The server must enforce the same rules for every request. Frontend filtering is not a security boundary.

Measurement history, context, events, and responses must link through canonical identities. Labels such as a person's name, room number, display text, or the position of a record in a list are not durable identity.

The existing typed frontend client boundary should remain the connection to backend services. Contract-valid mock responses may support frontend development, but components must not rely on hidden database structures or fabricate successful production responses from fixture data.

Any new outcome choice, responsibility transition, import status, notification status, or permission that needs a new schema must be coordinated in the shared data contract. Update matching backend models, frontend types, simulator data, and relevant tests together. This handoff's descriptions are business meanings, not a replacement set of undocumented enums.

The companion backend PRD proposes snapshots, continuous updates, measurements, and historical queries. Their implementation availability must be checked before a frontend feature is connected to live data. A well-designed mock experience is not proof that a real endpoint exists.

External integrations can later populate or update SYREN's internal records through backend adapters with explicit provenance and permissions. The core staff workflow must not depend on vendor-specific identifiers, browser-held integration keys, or a particular EHR login.

V1 must not include a marketplace, vendor configuration screens, care-platform authentication flows, automatic chart write-back, or a promise of universal interoperability. Those requirements are added after a specific service and supported workflow are identified.

# 18 Accessibility privacy and language

Staff must be able to complete essential tasks using supported touch input, a keyboard, and assistive technology. Meaningful control names, predictable focus, readable status changes, zoom and reflow, and accessible error explanations are required. WCAG 2.2 AA is the accessibility target; conformance requires testing the delivered implementation.

Information must not depend solely on a visual cue, hover behavior, sound, or a notification that can be dismissed. Staff must be able to inspect the underlying current work record. The teammate chooses the visual and interaction solutions.

Use plain care-work language and distinguish observation, interpretation, uncertainty, response intent, actual check, and resolution. Technical labels from ingestion, AI providers, raw sensors, databases, or integration transports do not belong in routine staff tasks.

No wording may claim a diagnosis, validated emergency detection, proof of safety, or a completed intervention that the records do not support. A lack of matching events means only that no matching events were returned for the stated scope and coverage.

Shared-client permissions must account for whether the device can be seen or held by visitors. Access to detailed context, original documents, exports, and administration must be separately controlled. A privacy action must not silently acknowledge care work or stop server alerting.

Do not place resident information, documents, care notes, credentials, or sensitive notification endpoints in public links, URLs, client analytics, screenshots used for development, console logs, crash reports, or test fixtures. Diagnostic collection must use appropriately minimized records.

Resident information must be requested and displayed within the current grant. Information from a previous facility, former area, or prior browser session must not remain attached to a newly approved client.

The initial language is plain US English. Dates, elapsed times, and due times must be understandable in the facility's time zone. Daylight-saving changes and repeated local times must not corrupt ordering or silently shift recorded actions. Units retain the backend's defined meaning.

The product must support the facility's authorized downtime and escalation process. A computer displaying SYREN must not imply that a person is continuously watching it or that every permitted clinical task is appropriate for every routine user.

# 19 Staff validation and release acceptance

Test with representative nursing assistants or caregivers, licensed nurses, charge staff, and temporary or agency users where those roles exist. Include day and night use, shared station computers, shared mobile devices, and realistic interruptions. Use synthetic or appropriately authorized test records.

The frontend must demonstrate the following task outcomes before release:

- A new routine user can use an approved client without creating a personal SYREN account.
- Administrator logout preserves permitted routine monitoring and response.
- The user can determine the client's assigned area and find a resident or room.
- Unanswered concerns and existing response intent are understandable without interpreting a graph.
- The user can access the observation time, evidence limits, and relevant care context for a concern.
- A missing reading is recognized as unavailable rather than zero or a reassuring normal value.
- An occupied room with unavailable monitoring remains discoverable.
- A multi-person or uncertain-assignment period cannot show confidently attributed resident measurements.
- A staff member can record a quick outcome without writing a routine narrative.
- “Could not check” does not produce a completed-check or resolved record.
- A response from a shared phone becomes visible to another authorized client.
- Simultaneous submissions and retries do not create duplicate or contradictory confirmed actions.
- A failed or unknown save cannot be mistaken for a completed action.
- An unresolved event and follow-up survive browser restart and shift change.
- A resolved event stays historical, while recurrence creates separate linked work.
- Notification opening and dismissal do not mark a resident checked.
- Actual notification delivery is demonstrated on each supported class, including the required unattended state.
- Denied permission, lost connectivity, and absence of a valid destination produce understandable recovery paths.
- A revoked client loses future server access, and a reachable client removes now-unauthorized content.
- Roster imports expose duplicate, unmatched, and conflicting records before active changes.
- An unsuccessful import preserves valid existing records.
- A room transfer preserves historical attribution and does not mix the former and new occupant's readings.
- Extracted medical context remains distinguishable from approved clinical information.
- Hospice context cannot accidentally become a universal instruction to stop notifications.
- A facility without a floor plan can complete all essential work.
- Essential tasks remain usable with keyboard, assistive technology, supported zoom, and supported touch input.

Record observed completion, help required, mistakes, duplicate entry, interruptions, missed or repeated work, and time spent per task. Establish quantitative usability targets from representative baseline testing rather than inventing a clinical response-time standard. Faster acknowledgment alone cannot establish better care.

Release requires working backend behavior, real synchronization and delivery evidence, staff comprehension, and appropriate facility validation. A mock demonstration or frontend build alone does not meet those conditions.

# 20 Delivery scope and decisions before live use

The teammate's handoff should include production frontend behavior against a documented client contract, development data that obeys that contract, automated coverage for critical permitted workflows, and evidence that the relevant staff tasks work on supported platforms. Visual design remains the teammate's responsibility.

The first operational scope includes facility and authorized shared access; room and resident records; supported private imports and context review; current monitoring and history; active concerns and quick responses; follow-up and handover; tested shared-device notifications; operational failure handling; and optional facility-plan support without dependence on it.

Separate deployments or connections for home-visiting hospice clinicians, family members, a home app, medication administration, billing, external EHR write-back, and native nurse-call workflows are outside this release. This scope does not prevent later product work in those areas.

Before live use, record the actual supported client platforms, chosen administrative authentication service, approved independent notification path, covered areas and backup responsibility, facility-approved policies and permissions, retention rules, backend import limits, and the facility's downtime procedure.

These are release configuration and validation requirements. They do not authorize the frontend teammate to invent medical thresholds, escalate every pending analysis, bypass notification-platform restrictions, or silently replace an unavailable service.

The first facility's staffing model and clinical response policy must be validated with that facility. Common behavior can be built in advance; who is permitted to perform a particular clinical action cannot be inferred solely from the words “assisted living,” “hospice,” or “nurse station.”

# 21 Research informing the requirements

The requirements above combine the founder's product decisions with engineering inferences from published staff research. The studies identify problems to address; they do not demonstrate that SYREN has reduced workload, improved clinical outcomes, or achieved regulatory compliance.

[Meehan 2020 nursing assistant user study](https://www.jnursinghomeresearch.com/2364-health-information-technology-use-among-nursing-assistants-in-long-term-care-a-user-study-of-a-touch-screen-point-of-care-system.html) involved 25 nursing assistants across three shifts at one Midwest skilled-nursing and rehabilitation facility. Participants reported excessive clicks, slow or uncertain saves, confusing documentation terminology, and shared-screen privacy issues. Their experience supports testing task clarity, saved-state comprehension, resident essentials, and privacy. It does not establish usability for every assisted-living population.

[Wild and colleagues 2021 retirement community monitoring study](https://www.jmir.org/2021/1/e18806/) involved 25 staff across seven Portland-area retirement communities. Only 11 staff accessed the dashboard during the study; reported barriers included login problems, a separate application, role ambiguity, and relevance. Its independent-living setting differs from urgent nursing response. It supports investigating whether the product fits actual responsibility and daily work rather than assuming dashboard availability produces use.

[Oosterom and colleagues 2023 nursing home handover study](https://pmc.ncbi.nlm.nih.gov/articles/PMC10333865/) examined nine nursing staff across five Dutch homes. Staff valued compact, structured current information while retaining conversation and resident-specific context. Its small organizational setting supports testing handover usefulness and information burden, rather than prescribing a universal handover process.

[Hospice employee work environment study published 2020](https://pmc.ncbi.nlm.nih.gov/articles/PMC7503310/) included 19 employees, including five nurses, at one Midwestern organization. Participants described ambiguous interruption urgency, duplicate dispatch, changing assignments, and documentation burden. Some examples concerned home visits, so travel and connectivity findings cannot be generalized to staffed-facility stations. Clear response meaning and coverage require direct facility validation.

[Bail and colleagues ACED IT co-design study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12666990/) was published online in 2025 and involved 20 participants in residential aged-care co-design and simulation. It examined tensions between simplicity and omission, clinical and psychosocial priorities, warnings and over-alerting, and integration and duplicate documentation. Simulation and small-sample feedback inform requirements; they do not establish a measured benefit from a deployed SYREN system.

[Hunt and colleagues 2021 hospice goals study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8055723/) interviewed 51 staff from four US nonprofit hospices, including a Midwest organization. Staff described documentation burden and the difficulty of capturing and finding individualized goals over time. This supports preserving dated source context and meaningful preferences. Its historical quality-measurement setting is not current regulatory guidance.

[WCAG 2.2](https://www.w3.org/TR/WCAG22/) provides the accessibility standard targeted by the delivered product. [Apple WebKit's web push documentation](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/) and [MDN's Push API documentation](https://developer.mozilla.org/en-US/docs/Web/API/Push_API) establish notification-platform prerequisites and mechanisms. Actual supported-device delivery still requires release testing.
