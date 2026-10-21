# SYREN clinic workspace

Next.js staff workspace for approved shared stations, laptops, phones and tablets. The initial view combines unresolved concerns with the covered resident/room roster. Routine staff need no personal account; facility administration is a separate flow.

This checkout runs an explicitly labeled **synthetic demonstration**. It does not provide production administrator authentication, server-enforced grants, live measurements, cross-device synchronization, private medical-document processing or background alert delivery. Do not enter real resident information. See [implementation status](../../docs/FRONTEND_IMPLEMENTATION_STATUS.md) for capability and acceptance evidence.

## Run and verify

```bash
pnpm install --frozen-lockfile
pnpm dev
pnpm test
pnpm lint
pnpm typecheck
pnpm build
```

The development server defaults to [localhost:3000](http://localhost:3000).

## Frontend boundaries

- `src/lib/monitoring`: existing typed monitoring contract.
- `src/lib/workspace`: composed staff-workspace client/provider and isolated synthetic journal.
- `src/features/workspace`: care overview, roster, resident/concern detail, quick outcomes, follow-up and handover.
- `src/features/workspace-admin`: facility/area/resident maintenance, CSV mapping/review/apply, shared-client access and alert-readiness states.
- `src/components/workspace-access`: synthetic route checks around retained setup/settings/device views. These checks are not a server security boundary.
- `src/app/providers.tsx`: explicit mock composition; real integration must replace it through the same typed interfaces after shared-contract agreement.

[Functional PRD](../../docs/FRONTEND_FUNCTIONAL_PRD.md), [design system](../../docs/design-system.md), [data contract](../../docs/DATA_CONTRACT.md), and [implementation plan](../../docs/superpowers/plans/2026-10-21-syren-staff-workspace.md) provide the handoff.

Only fictional fixtures and synthetic browser state are used. Same-origin tabs reconcile the demo journal; separate devices and browser profiles do not share it. Existing Scenario Lab remains under Demo tools. Resetting a scenario changes the underlying monitoring simulation, not the separate staff-workspace journal.

Existing synthetic station records created before action permissions were added load as view-only. Use demo administration → Shared devices to assign permitted routine actions explicitly. Existing care history remains available. Administration does not bypass the station’s routine action grant.
