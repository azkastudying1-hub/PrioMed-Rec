# Requirements Document

## Introduction

This feature improves the UI/UX of the PrioMed-Rec web application across all pharmacist-facing pages, from the login page through the main clinical workflow (worklist → patient detail → review) and supporting pages (dashboard, command center, audit trail, settings). The goal is to make the interface more professional, modern, clean, and aligned with healthcare application standards while preserving all existing workflows, functions, API calls, state management, routing, and backend components.

The application currently has a dual UI system: a newer design system in `web/src/uiux/` (primitives, clinical components, layout, tokens) used by WorklistPage and CasePage, and a legacy component library in `web/src/components/ui.tsx` used by DashboardPage, AuditLogPage, SettingsPage, CommandCenterPage, and ReviewConfirmationPage. The login page uses plain HTML elements without the design system. This feature unifies all pages under the existing design system, improves visual hierarchy for clinical data, strengthens accessibility, and standardizes loading/empty/error states without changing any backend, API, routing, or business logic.

## Glossary

- **PrioMed-Rec**: The AI-Powered Admission Risk Prioritization & Medication Reconciliation Support web application for hospital pharmacists.
- **Pharmacist**: A clinical pharmacist who uses the application to prioritize and review medication reconciliation cases.
- **DPJP**: Dokter Penanggung Jawab Pelayanan, the attending physician who makes final therapy decisions.
- **Design System**: The collection of visual tokens (`tokens.css`), UI primitives (`primitives.tsx`), clinical components (`clinical.tsx`), and layout (`layout.tsx`) in `web/src/uiux/`.
- **Legacy Components**: The older UI component library in `web/src/components/ui.tsx` and related files, which lacks the accessibility and visual consistency of the design system.
- **AppShell**: The application shell component in `layout.tsx` providing the sidebar navigation, topbar, and safety strip.
- **Worklist**: The prioritized list of medication reconciliation cases awaiting pharmacist review.
- **CasePage**: The patient detail workspace showing findings, medication comparison, SBAR draft, and review form.
- **Risk Score**: A numerical value (0–1) representing the ML model's predicted discrepancy likelihood for a patient.
- **Priority Tier**: The urgency classification assigned to a case: HIGH, MEDIUM, or LOW.
- **SBAR Draft**: An AI-generated Situation-Background-Assessment-Recommendation summary that the pharmacist must verify before use.
- **SHAP Explanation**: A breakdown of top feature contributions to the ML risk score, showing which factors drove the prediction.
- **Discrepancy**: A flagged difference between pre-admission and admission medication lists (e.g., omission, substitution, duplication).
- **High-Alert Medication**: A medication on the ISMP high-alert list requiring special attention during reconciliation.
- **SLA**: Service Level Agreement target time for reviewing a case by priority tier (HIGH: 2h, MEDIUM: 8h, LOW: 24h).
- **BPMH**: Best Possible Medication History, the structured form for collecting a patient's complete medication list.
- **Audit Trail**: A hash-chain log of pharmacist decisions (APPROVE, REJECT, EDIT, ESCALATE) for traceability.
- **ViewState**: The loading/empty/error/ready status of a page, used to render appropriate feedback states.
- **WCAG 2.1 AA**: Web Content Accessibility Guidelines at the AA conformance level, requiring 4.5:1 text contrast, keyboard navigation, and non-color-dependent status indicators.
- **Progressive Disclosure**: A UX pattern where secondary or technical information is hidden behind an expandable control, reducing initial cognitive load.
- **Alert Fatigue**: A condition where too many non-critical alerts desensitize the pharmacist, causing important alerts to be missed.
- **Click Target**: The minimum interactive area for touch/mouse, specified as 44×44px per WCAG 2.1 AA.
- **Focus Ring**: The visible outline shown when a keyboard user navigates to an interactive element.
- **SkipLink**: A keyboard-accessible link at the top of the page allowing users to jump directly to main content.

## Requirements

### Requirement 1: Login Page Design System Alignment

**User Story:** As a pharmacist, I want the login page to look professional and consistent with the rest of the application, so that I feel confident using a clinical-grade tool.

#### Acceptance Criteria

1. THE Login_Page SHALL render using the design system typography (Inter for body, Plus Jakarta Sans for headings), color tokens (--pmr-text, --pmr-bg, --pmr-surface), and border radius tokens (--pmr-radius-lg) from `tokens.css`
2. THE Login_Page SHALL replace the emoji brand icon (💊) with the HeartPulse icon from lucide-react used in the AppShell Brand component, styled with the same cyan-to-blue gradient background
3. THE Login_Page SHALL use the Input and Button primitives from `primitives.tsx` instead of plain HTML input and button elements
4. THE Login_Page SHALL display a safety notice stating that clinical decisions remain with the pharmacist, consistent with the safety strip in AppShell
5. WHEN the login form encounters an authentication error, THE Login_Page SHALL display the error message using the InlineAlert component from `primitives.tsx` with tone "danger" instead of a plain styled div
6. WHEN the login form is submitting, THE Login_Page SHALL show a loading spinner on the submit Button using the loading prop from the Button primitive
7. THE Login_Page SHALL include a SkipLink at the top of the page for keyboard users to skip to the login form
8. THE Login_Page SHALL maintain a minimum click target of 44×44px for the submit button via the Button primitive's min-h-12 size

### Requirement 2: Dashboard Page Design System Alignment

**User Story:** As a pharmacist, I want the dashboard to use the same visual language as the rest of the app, so that I can quickly interpret KPIs and system health without re-learning the interface.

#### Acceptance Criteria

1. THE Dashboard_Page SHALL import and use the Card, Badge, Button, and Heading components from `uiux/primitives.tsx` instead of the legacy `components/ui.tsx` and `components/TierBadge.tsx`
2. THE Dashboard_Page SHALL use the KpiCard component from `uiux/clinical.tsx` for displaying total cases, HIGH/MEDIUM/LOW counts, and SLA metrics
3. THE Dashboard_Page SHALL use the PriorityBadge component from `uiux/clinical.tsx` for tier distribution display instead of the legacy TierBadge
4. WHEN the worklist data is loading, THE Dashboard_Page SHALL render Skeleton components from `primitives.tsx` for the KPI cards instead of animate-pulse divs with hardcoded heights
5. WHEN the worklist data fails to load, THE Dashboard_Page SHALL render the ErrorState component from `primitives.tsx` with a retry action instead of a plain styled error div
6. THE Dashboard_Page SHALL use the SystemHealthDot status indicators with both color and text labels (OK/Error) so that status does not rely on color alone per WCAG 2.1 AA
7. THE Dashboard_Page SHALL display SLA status using consistent alert hierarchy colors: red for breach (--pmr-critical), amber for warning (--pmr-warning), green for OK (--pmr-success)

### Requirement 3: Worklist Visual Hierarchy and Readability

**User Story:** As a pharmacist, I want to understand patient priority within 3 seconds of looking at the worklist, so that I can triage the most urgent cases first.

#### Acceptance Criteria

1. THE Worklist_Page SHALL display each worklist row with a visual hierarchy ordered: priority tier badge, risk score, patient identity, top risk reason, SLA indicator, and workflow status
2. THE Worklist_Page SHALL render the risk score using the font-clinical-mono utility class (JetBrains Mono with tabular-nums) so that scores align for quick visual comparison
3. THE Worklist_Page SHALL use the PriorityBadge component from `clinical.tsx` with both a color indicator and a text label ("TINGGI", "SEDANG", "RENDAH") so that priority does not rely on color alone
4. WHEN a case has high-alert medications, THE Worklist_Page SHALL display a high-alert indicator badge with an icon (AlertTriangle from lucide-react) and a count, positioned prominently in the row
5. WHEN a case has an SLA breach, THE Worklist_Page SHALL display the SLA indicator with a red border and clock icon so that urgent cases are immediately distinguishable
6. THE Worklist_Page SHALL display a maximum of 7 columns in the desktop table view to reduce cognitive load per the reduce-cognitive-load principle
7. THE Worklist_Page SHALL provide a card-based layout for tablet/mobile viewports using the existing WorklistCard component, with priority badge and risk score at the top of each card

### Requirement 4: Patient Detail / CasePage Layout and Progressive Disclosure

**User Story:** As a pharmacist, I want the patient detail page to present findings progressively, so that I am not overwhelmed by all clinical data at once but can drill into details when needed.

#### Acceptance Criteria

1. THE Case_Page SHALL organize clinical content into clearly labeled tabbed sections: Findings, Medication Comparison, SBAR Draft, Review, and History
2. THE Case_Page SHALL use the Tabs component from `primitives.tsx` with keyboard-accessible ArrowLeft/ArrowRight navigation between tabs
3. THE Case_Page SHALL display the patient identity, priority badge, and risk score in a persistent header area that remains visible across all tab selections
4. WHEN the Findings tab is active, THE Case_Page SHALL display discrepancy findings as cards with discrepancy type, medication name, home vs admission values, and verification status
5. THE Case_Page SHALL render each discrepancy type label using consistent terminology: "OMISSION" for undocumented omission, "SUBSTITUTION" for possible substitution, "DUPLICATION" for potential duplication, "UNRESOLVED" for unresolved match
6. WHEN the SBAR Draft tab is active, THE Case_Page SHALL display the SBAR content with a visible AI-generated draft notice using the AiDraftNotice component from `clinical.tsx`
7. THE SBAR Draft section SHALL include a disclaimer stating that the pharmacist must verify the content and that final therapy decisions belong to the DPJP
8. WHILE the Medication Comparison tab is the active tab, THE Case_Page SHALL display pre-admission and admission medications side by side with matching highlighted and discrepancies flagged with colored badges; the side-by-side layout, matching highlight, and discrepancy flagging SHALL exist only while that tab is active and SHALL not be rendered or precomputed outside the active Medication Comparison view

### Requirement 5: Risk Explanation and SHAP Display

**User Story:** As a pharmacist, I want to understand why a patient received a particular risk score, so that I can validate the AI's reasoning before making a clinical decision.

#### Acceptance Criteria

1. THE Patient_Analysis_Page SHALL display the risk score using the RiskScoreBar component from `clinical.tsx` with a visual bar and numeric percentage
2. THE Patient_Analysis_Page SHALL display top SHAP feature contributions as a ranked list with feature name, contribution direction (positive/negative), and a visual bar showing relative magnitude
3. THE Patient_Analysis_Page SHALL render contribution values using the font-clinical-mono utility class for tabular number alignment
4. WHEN SHAP data is completely unavailable, THE Patient_Analysis_Page SHALL display "Belum tersedia"; WHEN SHAP data is incomplete or partial, THE Patient_Analysis_Page SHALL display "Perlu verifikasi"; THE Patient_Analysis_Page SHALL not hide the section or show blank space in either case
5. THE Patient_Analysis_Page SHALL include a label stating the model version and rule version that produced the explanation so the pharmacist knows which model generated the output
6. THE Patient_Analysis_Page SHALL display the AI-generated risk explanation with the AiDraftNotice component indicating the output is AI-generated and requires pharmacist verification

### Requirement 6: Pharmacist Review and Decision Form

**User Story:** As a pharmacist, I want to submit my review decision with clear options and feedback, so that my decision is recorded accurately in the audit trail.

#### Acceptance Criteria

1. THE Review_Form SHALL present four decision options as clearly labeled buttons: APPROVE (green/success), REJECT (red/danger), EDIT (blue/info), and ESCALATE (amber/warning) using the Button component with appropriate variants from `primitives.tsx`
2. THE Review_Form SHALL require a pharmacist note textarea when the action is REJECT or ESCALATE, using the Field and Textarea components from `primitives.tsx` with the required indicator
3. WHEN the pharmacist submits a review, THE Review_Form SHALL call the existing `recordDecision` or `submitReview` function passing the pharmacist note through the existing note parameter without changing the API contract or request structure
4. WHEN the review submission succeeds, THE Review_Form SHALL display a success feedback using the InlineAlert component with tone "success" confirming the decision was recorded
5. WHEN the review submission fails, THE Review_Form SHALL display an error feedback using the InlineAlert component with tone "danger" with a specific, actionable error message
6. THE Review_Form SHALL include a visible disclaimer that the pharmacist's decision is final and the AI output is advisory only, consistent with the AppShell safety strip message
7. THE Review_Form SHALL disable the submit button while a submission is in progress and show a loading spinner via the Button loading prop

### Requirement 7: Escalation Flow

**User Story:** As a pharmacist, I want to escalate a case to the DPJP or a senior pharmacist, so that complex cases receive appropriate review by the right person.

#### Acceptance Criteria

1. WHEN the pharmacist selects the ESCALATE action, THE Review_Form SHALL display an escalation form with a required reason field and an optional target recipient field
2. THE Escalation_Form SHALL use the Field, Select, and Textarea components from `primitives.tsx` for consistent form styling
3. THE Escalation_Form SHALL call the existing `submitReview` function with action "ESCALATE" and the escalation reason in the pharmacist_note field, without changing the API contract
4. WHEN escalation is submitted, THE Escalation_Form SHALL display a confirmation message stating the case has been escalated and the DPJP will be notified
5. THE Escalation_Form SHALL not modify the patient's priority tier, because escalation is an advisory action that does not override the ML risk classification

### Requirement 8: Audit Trail Page Consistency

**User Story:** As a pharmacist or auditor, I want the audit trail page to be consistent with the rest of the application, so that I can review pharmacist decisions in a familiar interface.

#### Acceptance Criteria

1. THE Audit_Log_Page SHALL import and use the Card, Badge, Button, Input, Select, EmptyState, ErrorState, and Skeleton components from `uiux/primitives.tsx` instead of the legacy `components/ui.tsx`
2. THE Audit_Log_Page SHALL use the SectionHeading component from `clinical.tsx` for the page title instead of the legacy Heading component
3. WHEN audit entries are loading, THE Audit_Log_Page SHALL render Skeleton components for the table rows instead of the legacy PageSkeleton component
4. WHEN no audit entries match the filter, THE Audit_Log_Page SHALL render the EmptyState component from `primitives.tsx` with a reset filter action button
5. THE Audit_Log_Page SHALL display action badges with both color and text labels (APPROVE as green with check icon, REJECT as red with x icon, EDIT as blue with pencil icon) so that status does not rely on color alone
6. THE Audit_Log_Page SHALL render timestamps using the font-clinical-mono utility class for alignment
7. THE Audit_Log_Page SHALL maintain the existing filter controls (search, date range, action type) without changing their behavior or API calls
8. THE Audit_Log_PageV2 SHALL follow the same design system alignment as the Audit_Log_Page for consistent presentation in live data mode

### Requirement 9: Loading, Empty, Error, and 404 States

**User Story:** As a pharmacist, I want clear feedback when the system is loading, when there is no data, or when something goes wrong, so that I always know the state of the application.

#### Acceptance Criteria

1. WHEN any page enters the "loading" ViewState, THE App SHALL render Skeleton components from `primitives.tsx` that approximate the layout of the expected content
2. WHEN any page enters the "empty" ViewState, THE App SHALL render the EmptyState component from `primitives.tsx` with a descriptive title, explanation, and an optional action button
3. WHEN any page enters the "error" ViewState, THE App SHALL render the ErrorState component from `primitives.tsx` with a descriptive error message and a retry button
4. WHEN a navigation request targets a non-existent page or route, THE App SHALL render a 404 state with a clear heading ("Halaman tidak ditemukan"), description, and a button to return to the worklist
5. WHEN clinical data was never captured or entered, THE App SHALL render the placeholder "Belum tersedia"; WHEN clinical data exists but requires pharmacist confirmation before use, THE App SHALL render the placeholder "Perlu verifikasi"; THE App SHALL not display blank space or placeholder symbols in either case
6. THE App SHALL ensure all loading skeletons, empty states, and error states maintain the design system's Card border-radius (--pmr-radius-xl) and shadow tokens for visual consistency

### Requirement 10: Design System Consistency

**User Story:** As a pharmacist, I want all pages to use consistent colors, spacing, typography, and components, so that I can navigate the application efficiently without visual jarring.

#### Acceptance Criteria

1. THE App SHALL use a consistent alert color hierarchy across all pages: critical/red-600 (--pmr-critical), high/orange-600, medium/amber-500 (--pmr-warning), low/green-600 (--pmr-success)
2. THE App SHALL use the font-display utility class (Plus Jakarta Sans) for all page headings and the font-clinical-mono utility class (JetBrains Mono) for all clinical numbers, risk scores, SLA values, and timestamps
3. THE App SHALL use consistent border radius tokens across all cards and containers: --pmr-radius (10px) for inputs/buttons, --pmr-radius-lg (14px) for cards, --pmr-radius-xl (18px) for modals
4. THE App SHALL use a consistent spacing scale of 4/8/12/16/24/32px (Tailwind's 1/2/3/4/6/8 scale) across all pages for padding, margins, and gaps
5. THE App SHALL use the Badge component from `primitives.tsx` with consistent tone values across all pages: "neutral", "info", "success", "warning", "danger", "critical", "teal"
6. THE App SHALL replace all imports from the legacy `components/ui.tsx` module with imports from `uiux/primitives.tsx` and `uiux/clinical.tsx` in pages that are currently using the legacy system

### Requirement 11: Accessibility Compliance

**User Story:** As a pharmacist who may use keyboard navigation or assistive technology, I want the application to be accessible per WCAG 2.1 AA, so that I can perform my duties without barriers.

#### Acceptance Criteria

1. THE App SHALL ensure all interactive elements (buttons, links, form inputs, tab controls) have a minimum click target of 44×44px
2. THE App SHALL ensure all text meets a minimum contrast ratio of 4.5:1 against its background per WCAG 2.1 AA
3. THE App SHALL provide visible focus rings on all interactive elements using the :focus-visible outline from the design tokens (--pmr-focus, --pmr-focus-ring)
4. THE App SHALL not rely on color alone to convey status; every status indicator SHALL include an icon and text label alongside its color
5. THE App SHALL provide keyboard-accessible navigation for the Tabs component with ArrowLeft and ArrowRight key support and proper aria-selected/aria-controls attributes
6. THE App SHALL include a SkipLink at the top of every page rendered within AppShell, allowing keyboard users to skip to the main content area
7. THE App SHALL ensure all form fields have associated label elements with proper htmlFor/id relationships and required indicators per the Field component from `primitives.tsx`
8. WHEN a modal is open, THE App SHALL trap focus within the modal, support Escape to close, and restore focus to the triggering element on close

### Requirement 12: Responsive Design

**User Story:** As a pharmacist who may use a tablet on rounds, I want the application to be usable on smaller screens, so that I can review cases away from my desk.

#### Acceptance Criteria

1. THE App SHALL provide an optimal layout for desktop/laptop screens (1280px and above) with the sidebar visible and multi-column content areas
2. THE App SHALL provide a usable layout for tablet screens (768px–1279px) with the sidebar collapsed into a slide-out drawer AND content areas reflowed to single or dual columns; the drawer collapse, content reflow, and overall usability SHALL each be satisfied, and the absence of any one SHALL constitute a violation
3. THE App SHALL maintain clinical data readability on tablet screens by using a minimum font size of 12px for clinical numbers and labels
4. THE App SHALL convert table-based layouts to card-based layouts on screens below 768px AND SHALL use the existing responsive breakpoint patterns (md:hidden, hidden md:block) to toggle between table and card views; the use of these specific breakpoint patterns is independently mandatory and the absence of either pattern SHALL constitute a violation
5. THE App SHALL ensure horizontal scrolling is available for wide tables on tablet screens rather than truncating or hiding clinical data columns
6. THE App SHALL maintain a minimum click target of 44×44px on all screen sizes, adjusting padding and spacing proportionally for touch usability

### Requirement 13: No Architecture or API Changes

**User Story:** As a developer maintaining PrioMed-Rec, I want the UI/UX improvements to not break existing architecture, API contracts, or workflows, so that the application remains stable and deployable.

#### Acceptance Criteria

1. THE App SHALL NOT delete any existing files, components, pages, routes, or functions from the codebase
2. THE App SHALL NOT change any backend FastAPI endpoints, request/response structures, ML models, rule engine logic, LLM service calls, or database schema
3. THE App SHALL NOT change the state-based routing mechanism in App.tsx (page state via useState, not react-router) or the Zustand auth store
4. THE App SHALL NOT replace the React framework, Tailwind CSS, TanStack Query, Zustand, or Vite build system
5. THE App SHALL NOT change the pharmacist workflow order: worklist → patient detail → review
6. THE App SHALL NOT make AI-generated content appear to change prescriptions, orders, or therapy decisions; all AI output SHALL remain advisory with explicit pharmacist-verification disclaimers
7. THE App SHALL make changes incrementally per page so that each change is reviewable independently
8. THE App SHALL prioritize existing function over design; when a design improvement conflicts with existing function, the existing function SHALL be preserved

### Requirement 14: Settings Page Design System Alignment

**User Story:** As a pharmacist or administrator, I want the settings page to be consistent with the rest of the application, so that I can manage high-alert medication lists and ward capacities in a familiar interface.

#### Acceptance Criteria

1. THE Settings_Page SHALL import and use the Card, Badge, Button, Input, Field, and Modal components from `uiux/primitives.tsx` instead of the legacy `components/ui.tsx`
2. THE Settings_Page SHALL use the SectionHeading component from `clinical.tsx` for section titles
3. WHEN the settings data is loading, THE Settings_Page SHALL render Skeleton components from `primitives.tsx` instead of the legacy PageSkeleton component
4. WHEN the settings data fails to load, THE Settings_Page SHALL render the ErrorState component from `primitives.tsx` with a retry action
5. THE Settings_Page SHALL use the Modal component from `primitives.tsx` with Escape-to-close, scroll-lock, and focus management for the edit and import dialogs
6. THE Settings_Page SHALL display verification status badges with both color and text ("Terverifikasi" / "Perlu verifikasi") so that status does not rely on color alone

### Requirement 15: Command Center Page Design System Alignment

**User Story:** As a pharmacy coordinator, I want the command center to use the same design system as other pages, so that I can monitor queue capacity and SLA risk in a consistent interface.

#### Acceptance Criteria

1. THE Command_Center_Page SHALL import and use the Card, Badge, Button, Input, EmptyState, and ErrorState components from `uiux/primitives.tsx` instead of the legacy `components/ui.tsx` and `components/TierBadge.tsx`
2. THE Command_Center_Page SHALL use the PriorityBadge component from `clinical.tsx` for tier display instead of the legacy TierBadge component
3. WHEN the command center data is loading, THE Command_Center_Page SHALL render Skeleton components from `primitives.tsx` approximating the KPI and chart layout
4. WHEN the command center data fails to load, THE Command_Center_Page SHALL render the ErrorState component from `primitives.tsx` with a retry action
5. THE Command_Center_Page SHALL use consistent alert hierarchy colors for SLA status indicators: red for breach, amber for warning, green for OK
6. THE Command_Center_Page SHALL maintain the existing SSE indicator, what-if form, and simulation panel functionality without changing their behavior or API calls

### Requirement 16: Review Confirmation Page Design System Alignment

**User Story:** As a pharmacist, I want the review confirmation page to use the same design system, so that I receive consistent visual feedback after saving a decision.

#### Acceptance Criteria

1. THE Review_Confirmation_Page SHALL import and use the Card, Button, and InlineAlert components from `uiux/primitives.tsx` instead of the legacy `components/ui.tsx`
2. WHEN a review is successfully saved, THE Review_Confirmation_Page SHALL display a success state using the InlineAlert component with tone "success" and a CheckCircle2 icon
3. THE Review_Confirmation_Page SHALL display the action label with consistent color coding: APPROVE as green/success, REJECT as red/danger, ESCALATE as amber/warning, EDIT as blue/info
4. THE Review_Confirmation_Page SHALL use the Button component from `primitives.tsx` for the return-to-worklist action with the secondary variant
5. THE Review_Confirmation_Page SHALL include a safety disclaimer stating the decision was recorded in the audit trail and that AI output is advisory only

### Requirement 17: Trust and Transparency Indicators

**User Story:** As a pharmacist, I want clear indicators of AI-generated content and data completeness, so that I can trust the system and know when I need to verify information manually.

#### Acceptance Criteria

1. WHEN AI-generated content is displayed (SBAR draft, risk explanation, discrepancy flags), THE App SHALL show the AiDraftNotice component from `clinical.tsx` indicating the content is AI-generated and requires pharmacist verification
2. THE App SHALL display a persistent safety banner in the AppShell topbar stating that clinical decisions remain with the pharmacist
3. WHEN clinical data is unavailable or incomplete, THE App SHALL display "Belum tersedia" (not yet available) or "Perku verifikasi" (needs verification) instead of hiding the section or showing blank space
4. THE App SHALL not hide incomplete or missing data behind a successful-looking interface; unavailable data SHALL be explicitly marked as such
5. WHEN an AI-generated risk explanation is displayed, THE App SHALL display the model version and rule version labels alongside that explanation so the pharmacist knows which model produced the output; WHEN no AI risk explanation is displayed, THE App SHALL not render model version or rule version labels
