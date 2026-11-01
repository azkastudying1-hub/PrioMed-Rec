# Implementation Plan: UI/UX Improvement

## Overview

This implementation plan migrates all pharmacist-facing pages of the PrioMed-Rec web application from the legacy component library (`components/ui.tsx`, `components/clinical.tsx`, `components/TierBadge.tsx`) and plain HTML to the unified `uiux/` design system (`primitives.tsx`, `clinical.tsx`, `layout.tsx`, `tokens.css`). The migration follows a 10-phase incremental approach: new components first, then page-by-page migration, then cross-cutting accessibility and responsive enforcement. No backend, API, routing, state management, or business logic changes are made. Legacy files are preserved (not deleted). Each phase builds on the previous one, with build verification (`tsc -b`, `vite build`) after each step.

## Tasks

- [x] 1. Create new components and enhance existing primitives
  - [x] 1.1 Enhance primitives.tsx: Add warning Button variant and Modal focus restoration
    - Add `warning` variant to the Button component variant map: `border-transparent bg-amber-600 text-white shadow-sm hover:bg-amber-700 active:bg-amber-800` (for ESCALATE action button)
    - Add focus restoration to the Modal component: save `document.activeElement` on open, restore focus to it on unmount via cleanup in the existing useEffect
    - _Requirements: 6.1, 11.8_
  - [x] 1.2 Create ShapContributionList and DataPlaceholder in clinical.tsx
    - Create `ShapContributionList` component: ranked list of SHAP contributions with visual bars (positive extends right in blue, negative extends left in teal), numeric values in `font-clinical-mono`, direction indicated by both color AND text label ("meningkatkan"/"menurunkan"), optional `modelVersion` and `ruleVersion` props rendered as labels below the list, `AiDraftNotice` included above, `DataPlaceholder` shown when contributions are empty or partial
    - Create `DataPlaceholder` component: `availability` prop ("unavailable" | "needs_verification" | "available"), renders "Belum tersedia" with Info icon on slate-50 background for unavailable, "Perlu verifikasi" with TriangleAlert icon on amber-50 background for needs_verification, renders children for available
    - Export `ShapContribution` and `DataAvailability` interfaces
    - _Requirements: 5.2, 5.3, 5.4, 9.5, 17.3, 17.4_
  - [x] 1.3 Create NotFoundState in pages.tsx
    - Create `NotFoundState` component using `EmptyState` from primitives with Compass icon
    - Title: "Halaman tidak ditemukan", description: "Halaman yang Anda cari tidak tersedia atau telah dipindahkan."
    - Action: `Button` variant "secondary" with label "Kembali ke Worklist" calling `onReturn` callback
    - _Requirements: 9.4_
  - [x] 1.4 Write unit tests for new components
    - Test `ShapContributionList` renders contributions with visual bars when data is provided
    - Test `ShapContributionList` renders "Belum tersedia" when contributions array is empty
    - Test `ShapContributionList` renders "Perlu verifikasi" when contributions are partial
    - Test `ShapContributionList` renders model version and rule version labels when provided
    - Test `DataPlaceholder` renders "Belum tersedia" for unavailable, "Perlu verifikasi" for needs_verification
    - Test `NotFoundState` renders heading and return-to-worklist button
    - Test `Button` warning variant applies amber styling classes
    - _Requirements: 5.2, 5.4, 9.4, 6.1_

- [~] 2. Checkpoint - Verify new components and build
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Migrate Login Page to design system (Phase 1)
  - [x] 3.1 Migrate LoginPage.tsx from plain HTML to uiux/ primitives
    - Replace `bg-slate-50` with `bg-[var(--pmr-bg)]` and use design system typography (`font-display` for headings, Inter body)
    - Replace emoji `💊` with `HeartPulse` icon from lucide-react in a gradient container matching AppShell Brand
    - Replace plain HTML `<input>` elements with `Field` + `Input` from primitives (with `htmlFor`/`id` associations)
    - Replace plain HTML `<button>` with `Button` primitive, size `lg` (min-h-12 = 48px), with `loading` prop
    - Replace error div with `InlineAlert` tone "danger" title "Gagal masuk"
    - Add `SkipLink` at top of page (anchors to login form)
    - Add `SafetyBanner compact` below the form
    - Preserve `handleSubmit`, `loginApi` call, `useAuthStore` login, `onSuccess` callback unchanged
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_
  - [x] 3.2 Write unit tests for LoginPage migration
    - Test LoginPage renders `Input` and `Button` from uiux/ primitives (not plain HTML)
    - Test LoginPage renders HeartPulse icon (not emoji)
    - Test LoginPage shows `InlineAlert` with tone "danger" on auth error
    - Test LoginPage shows Button loading spinner when submitting
    - Test LoginPage renders SkipLink
    - _Requirements: 1.2, 1.5, 1.6, 1.7_

- [x] 4. Migrate Dashboard Page to design system (Phase 2)
  - [x] 4.1 Migrate DashboardPage.tsx to uiux/ components
    - Replace local `KpiCard` function with `KpiCard` from `uiux/clinical.tsx`
    - Replace `TierBadge` import from `components/TierBadge.tsx` with `PriorityBadge` from `uiux/clinical.tsx`
    - Replace local `SystemHealthDot` with Badge `dot` prop + `aria-label` containing both color name and text ("OK"/"Error")
    - Replace `animate-pulse` loading divs with `Skeleton` from primitives approximating KPI card layout
    - Replace error div with `ErrorState` from primitives with `onRetry` callback
    - Replace local `getSlaTarget` with `SLA_TARGETS`, `isSlaBreached`, `slaTargetHours` from `uiux/clinical.tsx`
    - Update SLA bar colors to `bg-red-600` (critical), `bg-amber-500` (warning), `bg-emerald-600` (success)
    - Replace `Heading`, `Button`, `Card`, `Badge` from `components/ui.tsx` with equivalents from `uiux/primitives.tsx`
    - Replace `Heading` with `SectionHeading` from `uiux/clinical.tsx`
    - Preserve TanStack Query hooks, refetch interval, all data processing logic unchanged
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_
  - [-] 4.2 Write unit tests for DashboardPage migration
    - Test DashboardPage renders `KpiCard` from `uiux/clinical.tsx`
    - Test DashboardPage renders `PriorityBadge` (not legacy TierBadge)
    - Test DashboardPage renders `Skeleton` components on loading state
    - Test DashboardPage renders `ErrorState` with retry on error
    - Test `SystemHealthDot` renders both color and text label ("OK"/"Error")
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 5. Enhance Worklist visual hierarchy (Phase 3)
  - [x] 5.1 Enhance WorklistTable in pages.tsx
    - Add high-alert indicator badge with `AlertTriangle` icon from lucide-react and count when `priority_reasons` contains high-alert pattern; position prominently in row
    - Verify table has maximum 7 columns in desktop view
    - Add explicit short labels "TINGGI"/"SEDANG"/"RENDAH" to `PriorityBadge` compact mode (alongside existing color indicator)
    - Verify `font-clinical-mono` is applied to risk score percentage
    - Verify SLA indicator uses red border + clock/TriangleAlert icon for breach (existing `SlaIndicator`)
    - Verify `WorklistCard` for tablet/mobile has PriorityBadge and risk score at top
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_
  - [x] 5.2 Write unit tests for Worklist enhancements
    - Test WorklistTable renders high-alert badge with AlertTriangle icon and count when high-alert medications present
    - Test PriorityBadge renders text label "TINGGI"/"SEDANG"/"RENDAH" in compact mode
    - Test table column count does not exceed 7
    - _Requirements: 3.3, 3.4, 3.6_

- [x] 6. Enhance CasePage layout and progressive disclosure (Phase 4)
  - [x] 6.1 Enhance CasePage in pages.tsx
    - Verify exactly 5 tabs: Findings, Medication Comparison, SBAR Draft, Review, History
    - Verify persistent header with `PatientIdentity`, `PriorityBadge`, `RiskScoreBar` remains visible across all tab selections
    - Verify `Tabs` component has ArrowLeft/ArrowRight keyboard navigation and `aria-selected`/`aria-controls`
    - Verify Findings tab renders `FindingCard` components with discrepancy type, medication, home vs admission, verification status
    - Verify discrepancy labels use consistent terminology (OMISSION, SUBSTITUTION, DUPLICATION, UNRESOLVED)
    - Verify SBAR Draft tab includes `AiDraftNotice` component
    - Add explicit SBAR disclaimer: "Apoteker wajib memverifikasi konten ini. Keputusan terapi akhir tetap berada pada DPJP." as InlineAlert or within AiDraftNotice detail prop
    - Ensure Medication Comparison panel only renders when `activeTab === "compare"` (no precomputation via useMemo when tab inactive)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_
  - [-] 6.2 Write unit tests for CasePage enhancements
    - Test CasePage renders exactly 5 tabs with correct labels
    - Test SBAR disclaimer text is present
    - Test Medication Comparison panel does not render when compare tab is inactive
    - Test persistent header renders PatientIdentity, PriorityBadge, RiskScoreBar
    - _Requirements: 4.1, 4.7, 4.8_

- [~] 7. Checkpoint - Verify page migrations and build
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement Review Form and Escalation flow (Phase 6)
  - [x] 8.1 Enhance Review Form and add escalation sub-form in CasePage (pages.tsx)
    - Update 4 decision buttons: APPROVE (variant "success"), REJECT (variant "danger"), EDIT (variant "primary"), ESCALATE (variant "warning" from task 1.1)
    - Add required `Field` + `Textarea` for pharmacist note when action is REJECT or ESCALATE (with required indicator); note optional for APPROVE and EDIT
    - Verify `submitReviewV1` call passes `pharmacist_note` parameter through existing note parameter (no API contract change)
    - Verify `InlineAlert` tone "success" is shown on successful submission
    - Verify `InlineAlert` tone "danger" with specific actionable error message on failure
    - Add safety disclaimer: "Keputusan apoteker bersifat final. Output AI bersifat advisori saja."
    - Verify submit button uses `loading` prop to disable and show spinner during submission
    - Add escalation sub-form when ESCALATE is selected: required `Field` label "Alasan eskalasi" with `Textarea`, optional `Field` label "Penerima eskalasi" with `Select` (options: "DPJP (otomatis)", "Apoteker senior", "Koordinator farmasi")
    - Escalation submit calls `submitReviewV1` with action "ESCALATE" and reason in `pharmacist_note`
    - On successful escalation show `InlineAlert` tone "success": "Kasus telah dieskalasi. DPJP akan diberi tahu."
    - Verify escalation does NOT modify patient's `latest_tier`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 7.1, 7.2, 7.3, 7.4, 7.5_
  - [~] 8.2 Write unit tests for Review Form and Escalation
    - Test 4 decision buttons render with correct variants (success, danger, primary, warning)
    - Test required note Textarea appears when action is REJECT or ESCALATE
    - Test note is optional for APPROVE and EDIT
    - Test `InlineAlert` tone "success" shown on successful submission
    - Test `InlineAlert` tone "danger" shown on failed submission
    - Test submit button is disabled and shows spinner during loading
    - Test escalation sub-form renders with required reason field and optional recipient Select
    - Test escalation success shows confirmation message
    - Test escalation does not modify priority tier
    - _Requirements: 6.1, 6.2, 6.4, 6.5, 6.7, 7.1, 7.4, 7.5_

- [x] 9. Migrate PatientAnalysisPage for Risk and SHAP (Phase 5)
  - [x] 9.1 Migrate PatientAnalysisPage.tsx to design system
    - Replace legacy `RiskContributionChart` with `RiskScoreBar` + `ShapContributionList` from `uiux/clinical.tsx`
    - Apply `font-clinical-mono` utility class to contribution values
    - Use `DataPlaceholder` for missing SHAP data ("Belum tersedia") and partial SHAP data ("Perlu verifikasi")
    - Add model version and rule version labels from API response (`res.model_version`, `res.rule_version`) via `ShapContributionList` props
    - Replace legacy `VerificationNotice kind="ml"` with `AiDraftNotice` from `uiux/clinical.tsx`
    - Replace legacy `PriorityBadge` with `PriorityBadge` from `uiux/clinical.tsx`
    - Replace legacy `StatusBadge` with `WorkflowStatusBadge` from `uiux/clinical.tsx`
    - Replace legacy `PatientSummary` with `PatientIdentity` from `uiux/clinical.tsx`
    - Replace all legacy imports (`Card`, `Button`, `Badge`, `Heading`, `Input`, `Textarea`, `Field`, `Modal`, `EmptyState`, `ErrorState`, `PageSkeleton`, `Checkbox`) with equivalents from `uiux/primitives.tsx`
    - Replace `Heading` with `SectionHeading` from `uiux/clinical.tsx`
    - Preserve `analyzePatient` API call, `checkSafetyFlags` API call, `onDecision` callback, `onUpdatePatient` callback, discrepancy status update, SBAR copy, safety flag display, interaction review
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 10.6, 17.5_
  - [-] 9.2 Write unit tests for PatientAnalysisPage migration
    - Test `RiskScoreBar` and `ShapContributionList` render with SHAP data
    - Test `DataPlaceholder` renders "Belum tersedia" when SHAP data is unavailable
    - Test `DataPlaceholder` renders "Perlu verifikasi" when SHAP data is partial
    - Test model version and rule version labels render when AI explanation is displayed
    - Test model version and rule version labels do NOT render when no AI explanation
    - Test `AiDraftNotice` is displayed alongside risk explanation
    - _Requirements: 5.1, 5.2, 5.4, 5.5, 5.6, 17.5_

- [x] 10. Migrate Audit Pages to design system (Phase 7)
  - [x] 10.1 Migrate AuditLogPage.tsx to design system
    - Replace legacy imports with `Card`, `Badge`, `Button`, `Input`, `Select`, `EmptyState`, `ErrorState`, `Skeleton` from `uiux/primitives.tsx`
    - Replace legacy `Heading` with `SectionHeading` from `uiux/clinical.tsx`
    - Replace `PageSkeleton type="table"` with `Skeleton` components approximating table row layout
    - Replace legacy `EmptyState` with `EmptyState` from primitives with reset filter action button
    - Replace legacy `ErrorState` with `ErrorState` from primitives
    - Add action badges with icon + text + color: APPROVE (green + CheckCircle2), REJECT (red + XCircle), EDIT (blue + Pencil)
    - Apply `font-clinical-mono` to timestamps
    - Convert legacy `Select options={[...]}` to `Select` with children `<option>` elements (API difference)
    - Preserve existing filter controls (search, date range, action type) behavior and API calls
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_
  - [x] 10.2 Migrate AuditLogPageV2.tsx to design system
    - Replace inline-styled elements with `uiux/primitives.tsx` components (Card, Badge, Button, Input, Select, EmptyState, ErrorState, Skeleton)
    - Replace `ACTION_COLORS` map with `Badge` tones + icons (same mapping as AuditLogPage)
    - Use `Skeleton` for loading, `EmptyState` for empty, `ErrorState` for error
    - Apply `font-clinical-mono` to timestamps
    - Preserve `verifyAuditChain` mutation and all existing behavior
    - _Requirements: 8.8_
  - [ ] 10.3 Write unit tests for Audit pages migration
    - Test AuditLogPage renders `SectionHeading` (not legacy Heading)
    - Test action badges render with icons (CheckCircle2, XCircle, Pencil)
    - Test timestamps use `font-clinical-mono`
    - Test `EmptyState` with reset filter action renders when no entries match
    - Test `Skeleton` renders during loading
    - Test AuditLogPageV2 renders Badge with tone + icon for actions
    - _Requirements: 8.2, 8.3, 8.4, 8.5, 8.6, 8.8_

- [~] 11. Checkpoint - Verify audit and analysis migrations
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Standardize states, 404, and data placeholders (Phase 8)
  - [x] 12.1 Wire NotFoundState into App.tsx routing
    - Add `NotFoundState` fallback for invalid page state in the page router
    - Add 404 state for null `selectedV1Item` when user navigates to case view
    - Import `NotFoundState` from `pages.tsx`, render with `onReturn={() => setPage("worklist")}`
    - _Requirements: 9.4_
  - [~] 12.2 Standardize loading, empty, and error state patterns across pages
    - Verify all pages use `Skeleton` from primitives for loading states (approximate content layout)
    - Verify all pages use `EmptyState` from primitives for empty states (with descriptive title, explanation, optional action button)
    - Verify all pages use `ErrorState` from primitives for error states (with descriptive error message and retry button)
    - Verify all states maintain `Card` border-radius (`rounded-xl` = 14px) and shadow tokens for visual consistency
    - Patch any pages still using legacy patterns (animate-pulse divs, plain error divs, legacy PageSkeleton)
    - _Requirements: 9.1, 9.2, 9.3, 9.6_
  - [~] 12.3 Apply DataPlaceholder rules for missing clinical data
    - Use `DataPlaceholder` with `availability="unavailable"` for data that was never captured ("Belum tersedia")
    - Use `DataPlaceholder` with `availability="needs_verification"` for data that exists but requires pharmacist confirmation ("Perlu verifikasi")
    - Ensure no clinical data section renders blank space or placeholder symbols like "—"
    - Apply across CasePage (SHAP/SBAR sections), PatientAnalysisPage (SHAP section), and any other pages with potentially missing clinical data
    - _Requirements: 9.5, 17.3, 17.4_

- [x] 13. Migrate supporting pages to design system (Phase 9)
  - [x] 13.1 Migrate SettingsPage.tsx to design system
    - Replace legacy imports with `Card`, `Badge`, `Button`, `Input`, `Field`, `Modal` from `uiux/primitives.tsx`
    - Replace legacy `Heading` with `SectionHeading` from `uiux/clinical.tsx`
    - Replace `PageSkeleton type="form"` with `Skeleton` components approximating form layout
    - Replace legacy `ErrorState` with `ErrorState` from primitives with retry action
    - Use `Modal` from primitives with Escape-to-close, scroll-lock, and focus management for edit and import dialogs
    - Add icons to verification status badges: CheckCircle2 for "Terverifikasi", TriangleAlert for "Perlu verifikasi" (both color + text)
    - Add `htmlFor`/`id` associations to all `Field` + input pairs
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_
  - [x] 13.2 Migrate CommandCenterPage.tsx to design system
    - Replace legacy imports with `Card`, `Badge`, `Button`, `Input`, `EmptyState`, `ErrorState` from `uiux/primitives.tsx`
    - Replace `TierBadge` from `components/TierBadge.tsx` with `PriorityBadge` from `uiux/clinical.tsx`
    - Replace `PageSkeleton type="detail"` with `Skeleton` components approximating KPI/chart layout
    - Replace legacy `ErrorState` with `ErrorState` from primitives with retry action
    - Update SLA status indicators to consistent alert hierarchy: red (breach), amber (warning), green (OK)
    - Preserve SSE indicator, what-if form, and simulation panel functionality unchanged (only swap component imports)
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5, 15.6_
  - [x] 13.3 Migrate ReviewConfirmationPage.tsx to design system
    - Replace legacy imports with `Card`, `Button`, `InlineAlert` from `uiux/primitives.tsx`
    - Replace success state with `InlineAlert` tone "success" and `CheckCircle2` icon
    - Display action label with `Badge` and consistent color coding: APPROVE (success/green), REJECT (danger/red), ESCALATE (warning/amber), EDIT (info/blue)
    - Use `Button` variant "secondary" for return-to-worklist action
    - Add safety disclaimer: "Keputusan ini tercatat di jejak audit. Output AI bersifat advisori saja."
    - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_
  - [~] 13.4 Write unit tests for supporting pages migration
    - Test SettingsPage `Modal` has Escape-to-close and focus management
    - Test SettingsPage verification badges render with icon + text
    - Test CommandCenterPage renders `PriorityBadge` (not TierBadge)
    - Test CommandCenterPage SLA colors are consistent (red/amber/green)
    - Test ReviewConfirmationPage renders `InlineAlert` tone "success" with CheckCircle2
    - Test ReviewConfirmationPage action label Badge has correct tone per action type
    - Test ReviewConfirmationPage return button uses secondary variant
    - _Requirements: 14.5, 14.6, 15.2, 15.5, 16.2, 16.3, 16.4_

- [~] 14. Checkpoint - Verify supporting pages and states
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 15. Enforce accessibility, responsive, and trust indicators (Phase 10)
  - [~] 15.1 Enforce accessibility compliance across all pages
    - Ensure primary action buttons use `lg` size (min-h-12 = 48px) for 44px+ click targets
    - Add `min-h-11` (44px) to critical interactive elements that are below threshold
    - Verify `:focus-visible` focus rings on all interactive elements (buttons, links, inputs, tab controls)
    - Verify status indicators have icon + text label alongside color (PriorityBadge, WorkflowStatusBadge, SlaIndicator, audit action badges, SystemHealthDot)
    - Verify `Tabs` component supports ArrowLeft/ArrowRight keyboard navigation with `aria-selected`/`aria-controls`
    - Verify `SkipLink` is present at top of every page rendered within AppShell
    - Verify all form fields have associated `label` elements with `htmlFor`/`id` relationships and required indicators
    - Verify Modal traps focus, supports Escape to close, and restores focus to triggering element on close (from task 1.1)
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 12.6_
  - [~] 15.2 Verify responsive design patterns across all pages
    - Verify desktop layout (≥1280px): sidebar visible, multi-column content areas
    - Verify tablet layout (768px–1279px): sidebar collapsed to slide-out drawer, content reflowed to single/dual columns
    - Verify mobile layout (<768px): card-based layouts using `md:hidden`/`hidden md:block` patterns
    - Verify clinical data readability: minimum 12px font size for clinical numbers and labels
    - Verify horizontal scrolling available for wide tables on tablet (`overflow-x-auto` with `min-w-[...]`)
    - Verify 44px minimum click targets maintained on all screen sizes
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_
  - [~] 15.3 Apply trust and transparency indicators
    - Verify `AiDraftNotice` is displayed alongside AI-generated content: SBAR draft (CasePage), risk explanation (PatientAnalysisPage), discrepancy flags (Findings tab)
    - Verify safety banner in AppShell topbar is present and states clinical decisions remain with the pharmacist
    - Verify `DataPlaceholder` is used for unavailable ("Belum tersedia") and incomplete ("Perlu verifikasi") clinical data instead of hiding sections
    - Verify model version and rule version labels render only when AI risk explanation is displayed (not when absent)
    - Verify no incomplete or missing data is hidden behind a successful-looking interface
    - _Requirements: 17.1, 17.2, 17.3, 17.4, 17.5_

- [~] 16. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each phase
- The design uses TypeScript/React (not pseudocode); all code examples are in TSX
- Legacy files (`components/ui.tsx`, `components/clinical.tsx`, `components/TierBadge.tsx`) are preserved and NOT deleted
- No backend, API, routing, state management, or business logic changes (Requirement 13)
- Each page migration is incremental and independently reviewable (Requirement 13.7)
- Build verification (`tsc -b` and `vite build`) should pass after each task
- The design explicitly states PBT is not appropriate for this UI migration feature; unit tests and integration tests are used instead

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["3.1", "4.1", "9.1", "1.4"] },
    { "id": 2, "tasks": ["5.1", "10.1", "3.2", "4.2", "9.2"] },
    { "id": 3, "tasks": ["6.1", "10.2", "5.2"] },
    { "id": 4, "tasks": ["8.1", "13.1", "13.2", "13.3", "6.2", "10.3"] },
    { "id": 5, "tasks": ["8.2", "12.1", "13.4"] },
    { "id": 6, "tasks": ["12.2"] },
    { "id": 7, "tasks": ["12.3"] },
    { "id": 8, "tasks": ["15.1"] },
    { "id": 9, "tasks": ["15.2"] },
    { "id": 10, "tasks": ["15.3"] }
  ]
}
```
