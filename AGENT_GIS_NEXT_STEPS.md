# GIS Next Steps Plan

This file captures the implementation plan so work can be resumed later.

## Goal

Complete the remaining frontend stabilization for GIS workflows by adding true drawn-area selection, wiring it through operation payloads/presets/exports, and tightening summary-stats UX.

## Current Status Snapshot

- Backend support for geometry selection, extended summary metrics (`min`, `max`, `sum`), spatial predicate (`within`/`intersects`), async GIS task endpoints, presets, and GIS export endpoints is already present.
- Frontend has `All Sites` and `Viewport`-based geometry selection wired, async toggle, presets, and export controls.
- Remaining gap: no explicit user-driven drawn selection geometry flow in the map UI.

## Implementation Plan

1. Add drawn-area selection in map component
   - File: `frontend/src/components/maps/StudySiteMap.vue`
   - Add a draw interaction mode for rectangular/polygon selection.
   - Emit drawn geometry as GeoJSON coordinates in `EPSG:4326`.
   - Expose methods/events needed for parent page to enable, clear, and consume selection.

2. Add explicit selection mode state in Map page
   - File: `frontend/src/pages/Map.vue`
   - Replace binary viewport toggle with mode enum:
     - `all`
     - `viewport`
     - `drawn`
   - Update UI controls to switch modes clearly.
   - Add helper text/alerts when drawn mode is active but no geometry exists.

3. Wire selection mode into payload construction
   - File: `frontend/src/pages/Map.vue`
   - Update `buildStudySiteSelection()` to map mode -> selection payload:
     - `all` -> `{ type: 'all' }`
     - `viewport` -> `{ type: 'geometry', geometry: viewportPolygon }`
     - `drawn` -> `{ type: 'geometry', geometry: drawnPolygon }`
   - Ensure all operation builders consume the same helper.

4. Keep presets/export aligned with new mode
   - Files:
     - `frontend/src/pages/Map.vue`
     - `frontend/src/stores/gis.ts` (if typing adjustments are needed)
   - Ensure save/load preset restores selection mode appropriately.
   - Ensure `exportCurrentOperation()` uses the same payload builder without divergence.

5. Add summary spatial predicate control
   - File: `frontend/src/pages/Map.vue`
   - Add UI selector/toggle for summary spatial predicate:
     - `within`
     - `intersects`
   - Include predicate in summary payload when region spatial filter is used.

6. Improve summary row formatting
   - File: `frontend/src/pages/Map.vue`
   - Update `formatSummaryRow()` so dynamically added metric aliases (including `min/max/sum`) are displayed consistently instead of hardcoding only `site_count`/`avg_confidence`.

7. Expand frontend tests for new behavior
   - File: `frontend/src/tests/pages/Map.spec.ts`
   - Add tests for:
     - Selection mode -> payload mapping (`all`, `viewport`, `drawn`).
     - Drawn mode fallback behavior when geometry missing.
     - Summary predicate inclusion in payload.
     - Preset application restoring selection mode.
     - Summary row formatter handling additional metric aliases.

8. Run targeted validation
   - From `frontend/`:
     - `pnpm test -- src/tests/pages/Map.spec.ts src/tests/stores/gis.spec.ts src/tests/stores/studySites.spec.ts`
   - Optionally run `pnpm lint` if local lint toolchain is healthy.

## Notes / Risks

- Existing lint config in this environment has previously failed due an oxlint plugin rule mismatch (`no-multiple-slot-arg`), so lint may fail independently of code changes.
- Backend test execution remains dependent on local Postgres role setup; this plan is frontend-focused.

## Definition of Done

- Drawn-area selection can be created, cleared, and used as GIS operation input.
- Selection mode is explicit and stable across operation runs.
- Presets and exports reflect the same payload logic as run operations.
- Summary predicate is user-selectable and serialized correctly.
- Targeted frontend tests pass for the modified paths.
