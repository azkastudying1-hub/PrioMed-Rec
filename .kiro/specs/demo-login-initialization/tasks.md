# Implementation Plan

## Overview

Tasks mengimplementasikan perbaikan untuk demo login initialization bug berdasarkan design.md dan bugfix.md. Fokus pada tiga layer: dokumentasi setup, backend error detection, dan frontend enhancement. Pendekatan menggunakan bug condition methodology dengan property-based testing untuk memastikan tidak ada regresi pada authentication logic yang sudah berjalan.

**Bug/Issue yang ditangani:**
- Layer 1: Dokumentasi README tidak menjelaskan mandatory seed step
- Layer 2: Backend tidak mendeteksi empty database + demo credentials
- Layer 3: Frontend tidak menampilkan informative error message untuk setup guidance

**Implementation Strategy:**
1. Buat exploration tests untuk memverifikasi bug condition pada unfixed code
2. Buat preservation tests untuk memastikan existing auth logic tidak berubah
3. Implement Layer 1 (README + Documentation)
4. Implement Layer 2 (Backend Error Detection)
5. Implement Layer 3 (Frontend Enhancement)
6. Verify semua tests pass dan no regressions

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1", "2"] },
    { "wave": 2, "tasks": ["3"] },
    { "wave": 3, "tasks": ["4", "5", "6"] },
    { "wave": 4, "tasks": ["7", "8"] },
    { "wave": 5, "tasks": ["9", "10", "11"] }
  ]
}
```

## Tasks

---

### WAVE 1: EXPLORATORY & PRESERVATION TESTING

- [ ] 1. Write bug condition exploration test
  - [ ] 1.1 Create test file `tests/test_demo_login_exploration.py` with bug condition assertions
    - _Goal_: Verify bug manifests on unfixed code (generic error for demo credentials on empty DB)
    - _Acceptance_: Test confirms "Username atau password salah." not informative
    - _Requirements: 1.1, 1.2, 1.3_

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - [ ] 2.1 Create test file `tests/test_demo_login_preservation.py` with baseline behavior capture
    - _Goal_: Capture existing auth behavior to prevent regressions
    - _Acceptance_: Valid credentials still work, invalid credentials still fail with generic message
    - _Requirements: 3.1, 3.2, 3.3_

---

### WAVE 2: LAYER 1 - DOCUMENTATION

- [ ] 3. Update README.md with quick start guide & seed instruction
  - [ ] 3.1 Add "Quick Start" section with 8 mandatory steps including seed_demo.py
    - _Goal_: Provide explicit setup instructions for first-time users
    - _Acceptance_: README contains clear step-by-step guide
    - _Requirements: 2.1_
  - [ ] 3.2 Add "Demo Credentials" section listing all demo users
    - _Goal_: Document default demo credentials after seeding
    - _Acceptance_: Table with username/password for each demo role
    - _Requirements: 2.1_
  - [ ] 3.3 Add "Troubleshooting" section for login failures
    - _Goal_: Guide users when they encounter seed_demo.py error
    - _Acceptance_: Clear explanation of empty database scenario and solution
    - _Requirements: 2.1_

---

### WAVE 3: LAYER 2 - BACKEND ERROR DETECTION

- [ ] 4. Add `_is_database_empty()` helper function
  - [ ] 4.1 Create helper function in `backend/api/routes/v1/auth.py`
    - _Goal_: Check if User table is empty (first-run state)
    - _Acceptance_: Function returns True on empty DB, False on seeded DB
    - _Requirements: 2.2_

- [ ] 5. Enhance login endpoint error detection
  - [ ] 5.1 Add DEMO_USERNAMES constant with demo credentials list
    - _Goal_: Identify demo credential attempts
    - _Acceptance_: Constant contains ["apoteker1", "ttk1", "koordinator1", "admin"]
    - _Requirements: 2.2_
  - [ ] 5.2 Modify login endpoint to detect empty DB + demo credentials
    - _Goal_: Return informative error only for demo users on empty DB
    - _Acceptance_: Error contains "seed_demo.py" for demo on empty DB, generic error for others
    - _Requirements: 2.2_

- [ ] 6. Add unit tests for backend error detection
  - [ ] 6.1 Create `tests/test_auth_empty_db.py` with backend tests
    - _Goal_: Verify backend correctly detects and reports seed need
    - _Acceptance_: Tests cover demo/non-demo credentials on empty/seeded DB
    - _Requirements: 2.2_

---

### WAVE 4: LAYER 3 - FRONTEND ENHANCEMENT

- [ ] 7. Parse and display seed instruction in LoginPage
  - [ ] 7.1 Update `web/src/pages/LoginPage.tsx` error handling
    - _Goal_: Show special warning alert when seed_demo.py mentioned in error
    - _Acceptance_: InlineAlert displays with seed instruction when error contains "seed_demo.py"
    - _Requirements: 2.2_

- [ ] 8. Add collapsible setup help section
  - [ ] 8.1 Add collapsible details element with setup instructions in LoginPage
    - _Goal_: Provide optional quick reference for first-time users
    - _Acceptance_: Collapsible section appears below login form with setup steps
    - _Requirements: 2.2_

---

### WAVE 5: VERIFICATION

- [ ] 9. Verify bug condition exploration test now passes
  - [ ] 9.1 Re-run task 1 tests on fixed code
    - _Goal_: Confirm empty DB + demo credentials now returns seed instruction
    - _Acceptance_: All assertions pass, error message contains "seed_demo.py"
    - _Requirements: 2.1, 2.2_

- [ ] 10. Verify preservation tests still pass
  - [ ] 10.1 Re-run task 2 tests on fixed code
    - _Goal_: Confirm no regressions in auth behavior
    - _Acceptance_: Valid credentials still authenticate, invalid still fail appropriately
    - _Requirements: 3.1, 3.2, 3.3_

- [ ] 11. Final integration testing & checkpoint
  - [ ] 11.1 Test complete fresh setup flow: empty DB → seed → login success
    - _Goal_: Verify entire user journey works correctly
    - _Acceptance_: User receives clear guidance through whole process
    - _Requirements: 2.1, 2.2_
  - [ ] 11.2 Verify security: no username enumeration in error messages
    - _Goal_: Confirm security best practices maintained
    - _Acceptance_: All error messages are generic or seed-related, no existence checks
    - _Requirements: 3.2_
  - [ ] 11.3 Verify documentation accuracy: README guide is followable
    - _Goal_: Confirm setup instructions are clear and complete
    - _Acceptance_: New user can follow steps without additional knowledge
    - _Requirements: 2.1_

---

## Notes

- Tasks 1–2 are **Property-Based Tests** yang harus ditulis SEBELUM fix diterapkan
- Task 1 (Bug Condition) — assertions mengkonfirmasi bug condition exist pada unfixed code
- Task 2 (Preservation) — diharapkan PASS pada kode unfixed sebagai baseline behavior
- Tasks 3–8 adalah implementasi fix dengan urutan: dokumentasi → backend → frontend
- Tasks 9–11 menggunakan test yang SAMA dari tasks 1–2 (bukan test baru) untuk verifikasi setelah fix
- Semua fix adalah **minimal targeted changes** — fokus hanya pada onboarding UX, tidak mengubah core auth logic
- Security requirement 3.2 adalah kritis: error messages tidak boleh mengungkap existence username, hanya demo credentials mendapat special message
- Frontend enhancement (tasks 7–8) adalah recommended untuk better UX namun bukan hard requirement

