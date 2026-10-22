# SYREN UI/UX Pro Max visual refinement

## Reuse report

- Requested capability: a more considered clinic aesthetic while maintaining full functionality.
- Current implementation matches: AppShell, shared control primitives, care-shared.tsx and care-workspace.module.css already implement the complete synthetic staff workspace.
- Contract/documentation matches: Native Care V5 and the functional PRD preserve scope, lifecycle, explicit unavailable states and shared-device access. No schema change is needed.
- History matches: PR21/fc13b28 established workflows; PR22/12d2977 and PR23/4ff7d90 established the current visual system and green completed history.
- Issue/PR matches: only backend PR20 remains open, with no apps overlap. No issues or competing frontend work were found.
- Verdict: extend.
- Recommended implementation boundary: clinic tokens, shell, shared controls, care/admin styles, design guide/download/reference. Keep clients, lifecycle, data, permissions and hardware boundaries intact.
- Evidence gaps: Graphify executable was previously unavailable. No representative nursing-staff or assistive-technology study is implied.

## Design decisions

The explicitly requested UI/UX Pro Max skill was read and its required design-system search run for a calm, accessible healthcare monitoring dashboard. Additional style, senior-care color and Next.js searches informed the adaptation. Reject the generated hero/features/CTA pattern: this is an operational workspace. Retain native system fonts rather than introducing remote font dependencies. Deepen the suggested cyan into a contrast-checked blue-teal action role; reserve green for supplied positive state/completed workflow and red/amber for actual semantic attention.

Create a stronger blue-slate navigation frame, clean light content, deliberate room-first row alignment, consistent control geometry and restrained elevation. Use existing SVGs. Avoid gradients, decorative illustrations, gratuitous pills/tiles, fabricated charts and animation that shifts layout. Preserve actual useful density and full labels. Resolved history must never inherit active urgency treatment. Mobile controls remain comfortably reachable, with current response work before evidence and metadata.

## Work and acceptance

1. Capture the baseline and adjust canonical tokens/shared styles coherently, without appended override piles or alternate component trees.
2. Inspect the actual desktop result; refine type, contrast, spacing and status hierarchy. Inspect active/completed concerns, resident, administration and handover.
3. Verify 375, 768, 1024 and 1440px widths, visible keyboard focus, hover stability and reduced motion. Fix clipping/overlap. Keep synthetic demo state and disclosures intact.
4. Keep canonical guide, download and reference aligned; run tests, lint, typecheck and build. Numerical contrast checks supplement visual QA and do not establish full WCAG conformance.
5. Review, create a PR, request the configured review and merge under standing user authorization. Disclose unavailable review services accurately. Preserve the primary hardware checkout and backend PR20.
