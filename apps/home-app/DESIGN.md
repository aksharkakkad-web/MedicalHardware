# Adaptive Care Home Design System

## Creative direction: Morning Window

The home experience should feel like opening a curtain and getting one calm, truthful view of the day. It is warm, bright, personal, and quiet. It does not borrow the clinic console’s work-queue density or operational language.

## Visual language

- **Canvas:** warm daylight `#f7f5ef`.
- **Primary surface:** soft white `#fffefa`.
- **Text:** charcoal `#242522`; supporting copy `#686a64`.
- **Action blue:** clear sky `#2467d6`, reserved for navigation and actions.
- **Steady green:** `#256c58` on `#e2f2eb`.
- **Attention amber:** `#8a5710` on `#fff0d3`.
- **Important coral:** `#9c3d35` on `#fde9e5`.
- **Unavailable gray:** `#5f6561` on `#ecefec`.
- **Borders:** warm gray `#dfdfd8`.

Use Geist throughout. Page titles are large and gently tight; body copy is at least 0.9rem with generous line spacing. Status language is the visual hero, not numbers.

## Layout rules

- Desktop content is capped near 72rem, with a light header and three simple destinations: Today, Updates, and Routines.
- Mobile uses the same destinations in a persistent bottom bar so the family member always knows where they are.
- Begin with one large status window, followed by one continuous trend sheet and then recent updates.
- Do not create a clinic-style table, alarm queue, device dashboard, or grid of tiny metrics.
- Detail pages reveal: what changed, what the system noticed, what remains unknown, and what the family can do next.

## Components

- **Status window:** a large steady/attention/away/limited/unavailable statement with a plain explanation and last update.
- **Trend sheet:** three quiet rows with a label, plain-language direction, short explanation, and small seven-day sparkline when available.
- **Update record:** headline, time, importance words, and one direct path to the explanation.
- **Feedback choice:** full-row radio options written as ordinary answers: expected, not expected, or unsure.
- **Routine record:** current context shown as a readable sentence with source/time and a quiet “No longer current” action.

## Interaction and safety

- Every action has a visible focus state and at least a 44px target.
- Important meaning always uses words in addition to color.
- Saving feedback or routines produces a plain confirmation in a live region.
- Loading, empty, error, limited, and unavailable states never imply reassurance.
- Motion is limited to 150ms control feedback and disappears under reduced motion.

## Data boundary

The home client returns family-safe presentation models for this app. They are not a second Product API contract. Real-data wiring must adapt the published shared domain objects into these views, and must wait for the backend to publish the missing home/trend data rather than inventing it in the UI.

## Signature rule

**The One Calm Answer Rule:** Every main screen begins with one sentence a family member can understand immediately. Supporting evidence follows below; it never competes with the answer.

## Avoid

- Hospital language, raw sensor names, confidence percentages, or staff workflow controls.
- “Safe,” “all clear,” diagnoses, or invented medical thresholds.
- Decorative gradients, glass panels, excessive pills, or equal-weight metric mosaics.
- Cute illustrations that weaken the seriousness of an important update.
