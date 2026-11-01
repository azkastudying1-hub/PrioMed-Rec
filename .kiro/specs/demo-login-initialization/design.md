# Demo Login Initialization — Bugfix Design

## Overview

Pengguna baru mengalami kebingungan saat pertama kali setup PrioMed-Rec karena tidak menyadari bahwa database perlu di-seed dengan data demo sebelum dapat login. Meskipun backend mengembalikan error 401 yang valid ("Username atau password salah"), pesan ini tidak informatif tentang penyebab sebenarnya: database kosong tanpa akun demo.

Strategi fix adalah tiga pilar:
1. **Dokumentasi Setup Jelas**: README yang menjelaskan langkah mandatory seeding database
2. **Error Message Informatif**: Pesan login yang mendeteksi database kosong dan membimbing user ke seed script
3. **Automation Optional**: Opsi otomatis seed saat startup pertama (untuk developer experience yang lebih smooth)

Pendekatan ini berfokus pada UX: membuat onboarding lebih jelas, informatif, dan dipandu tanpa mengubah core authentication logic.

## Glossary

- **Bug_Condition (C)**: User mencoba login dengan demo credentials pada database kosong (tidak ada user atau hanya system users)
- **Property (P)**: User menerima pesan yang jelas tentang perlu seed database, dengan instruksi atau link ke dokumentasi
- **Preservation**: Authentication logic untuk credentials valid/invalid tetap tidak berubah; security tidak berkurang; error handling tetap robust
- **seed_demo.py**: Script di `scripts/seed_demo.py` yang populate database dengan akun demo dan data scenario S1–S10
- **LoginPage.tsx**: Halaman login di `web/src/pages/LoginPage.tsx` yang menangani form input dan menampilkan error
- **auth/login endpoint**: FastAPI POST `/api/v1/auth/login` di `backend/api/routes/v1/auth.py` yang memproses login request
- **Empty Database State**: SQLite database tidak memiliki user records kecuali system default (jika ada)
- **Demo Credentials**: Default credentials untuk testing (e.g., apoteker1 / demo1234, ttk1 / demo1234, etc.)

## Bug Details

### Bug Condition

Bug manifests ketika user pertama kali clone repository, setup environment, jalankan aplikasi, dan coba login dengan demo credentials (apoteker1 / demo1234) **pada database yang belum di-seed**.

**Formal Specification:**

```
FUNCTION isBugCondition(input)
  INPUT: input of type {username: string, password: string}
  OUTPUT: boolean
  
  RETURN database.User WHERE username = input.username IS EMPTY
         AND no auto-seeding has occurred on first startup
         AND user expects credentials from documentation to work
         AND input contains demo credentials (apoteker1–4, ttk1, koordinator1, admin)
END FUNCTION
```

### Examples

**Example 1: Fresh clone, direct login attempt**
- Setup: Clone repo, setup `.env`, start backend/frontend, database is empty
- Action: User enters "apoteker1" / "demo1234" in login form (from inline hint or docs)
- Current Behavior: Login fails with "Username atau password salah." — user confused, doesn't know database needs seeding
- Expected Behavior: Error message informs user: "Akun demo belum diinisialisasi. Jalankan seed script terlebih dahulu: `python scripts/seed_demo.py`"

**Example 2: Developer follows setup guide but misses seed step**
- Setup: Clone repo, install dependencies, database initialized but empty
- Action: Developer runs `docker-compose up` or `npm run dev + python main`, tries demo login
- Current Behavior: Generic 401 error, developer confused whether credentials wrong or setup incomplete
- Expected Behavior: Clear error + link to setup documentation explaining seed step

**Example 3: Seed script run successfully, credentials now work**
- Setup: Developer runs `python scripts/seed_demo.py`, database populated
- Action: User enters "apoteker1" / "demo1234"
- Current Behavior: Authentication succeeds, user is redirected to dashboard
- Expected Behavior: Same (no change to normal flow)

**Example 4: Invalid credentials after seeding**
- Setup: Database seeded with demo users
- Action: User enters "apoteker1" / "wrongpassword"
- Current Behavior: "Username atau password salah." (unchanged)
- Expected Behavior: Same (security best practice: don't reveal if username exists)

**Example 5: Edge case — database has some users but not demo user**
- Setup: Database exists with production/real users, demo users not present
- Action: User tries "apoteker1" / "demo1234"
- Current Behavior: Generic 401 error
- Expected Behavior: Same as Example 1 (detect missing demo credentials specifically)

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Authentication logic must remain unchanged: valid credentials → JWT token, invalid → 401
- Security posture unchanged: error messages do NOT reveal whether username exists (to prevent user enumeration)
- Database schema not modified: User table structure stays the same
- Existing valid user logins continue to work exactly as before
- Refresh token, logout, and token expiry behavior unchanged
- API contract for `/auth/login` endpoint stays the same

**Scope:**

All inputs that do NOT involve fresh database + demo credentials should be completely unaffected:
- Login with valid non-demo credentials (production users, test users not part of seed)
- Login after database is seeded
- Token refresh, logout, session management
- Other authentication endpoints (`/refresh`, `/logout`, `/me`)

## Hypothesized Root Cause

Based on the bug description and code review, the root cause is a **workflow mismatch**, not a bug in code:

1. **Missing Mandatory Step Documentation**: README and setup guide don't explicitly state that `python scripts/seed_demo.py` must run before first login attempt
   - New users follow along, set up environment, start app, then get confused on login

2. **Uninformative Error Message**: Backend returns generic 401 ("Username atau password salah") for all auth failures
   - Doesn't distinguish between: wrong password, user doesn't exist, database empty
   - User has no way to know the root cause

3. **No Detection of Empty Database State**: Backend doesn't detect if database is in "first-run" state (empty user table)
   - Could return special error code or message when specifically demo credentials fail on empty DB

4. **Frontend Doesn't Guide to Next Steps**: LoginPage shows demo credentials but no indication that seed script must run first
   - Hint at bottom says "Akun Demo:" but not "Jalankan seed_demo.py terlebih dahulu"

5. **No Automation for Developer Workflow**: Unlike some frameworks (e.g., Django `migrate` + `createsuperuser`), setup requires manual seed script
   - Could be automated on first startup or in Docker entrypoint

## Correctness Properties

Property 1: Bug Condition - Clear Setup Instructions for First-Time User

_For any_ login attempt with demo credentials on a fresh (empty database), the system SHALL display an error message that:
- Explicitly states that demo data must be seeded
- Includes clear instruction to run `python scripts/seed_demo.py`
- Provides a link or reference to the setup documentation

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation - Normal Authentication Behavior Unchanged

_For any_ login attempt with valid credentials (after database is seeded OR with production users), the system SHALL authenticate successfully and return JWT tokens exactly as before, preserving all existing security and session management behavior.

**Validates: Requirements 3.1, 3.2, 3.3**

## Fix Implementation

### Solution Strategy

Implement a **three-layer approach** to make onboarding clearer without changing authentication logic:

### Changes Required

**Layer 1: Documentation (README + Setup Guide)**

**File**: `README.md`

**Changes**:
1. Add explicit "Quick Start" section with mandatory steps in order:
   - Clone repo
   - Install dependencies (`pip install -r requirements.txt`, `npm install` in `web/`)
   - Setup `.env` from `.env.example`
   - **[MANDATORY]** Run `python scripts/seed_demo.py` to initialize demo database
   - Start backend/frontend

2. Create a new section "First-Time Setup Troubleshooting":
   - If login fails with "Username atau password salah", check that seed script was run
   - Link to `scripts/seed_demo.py` documentation

3. Add a "Demo Credentials" section listing:
   - apoteker1 / demo1234
   - ttk1 / demo1234
   - koordinator1 / demo1234
   - admin / admin1234
   - Note: These credentials only work after `python scripts/seed_demo.py` is executed

**Layer 2: Enhanced Error Detection (Backend)**

**File**: `backend/api/routes/v1/auth.py`

**Function**: `login` endpoint (lines 111–150)

**Specific Changes**:
1. Add helper function `_is_database_empty()` that checks if User table has any non-system users:
   - Query count of User records where is_active = True
   - Return True if count = 0 OR only contains system placeholder users

2. After password verification fails (line 123), add check:
   ```
   IF login failed AND (username in DEMO_CREDENTIALS_LIST) AND _is_database_empty():
       RETURN 401 with special message:
       "Akun demo belum diinisialisasi. Jalankan: python scripts/seed_demo.py"
   ELSE:
       RETURN 401 with generic message:
       "Username atau password salah."
   ```

3. Add a constant `DEMO_USERNAMES = ["apoteker1", "ttk1", "koordinator1", "admin"]` at module level for detection

4. Keep generic error message for all other failures (security best practice)

**Layer 3: Enhanced Frontend Message (Optional but Recommended)**

**File**: `web/src/pages/LoginPage.tsx`

**Function**: Error message display (lines 70–77)

**Specific Changes**:
1. In `handleSubmit`, parse error message from backend response
2. If error contains "seed_demo.py" substring, display a special InlineAlert with tone "warning" (informational):
   - Title: "Akun Demo Belum Diinisialisasi"
   - Body: Display full message from backend + visual instruction
   - Include optional link to documentation or terminal command hint

3. Show a collapsible "Setup Help" section if login fails:
   ```
   <details>
     <summary>Butuh bantuan setup?</summary>
     <p>Jalankan di terminal project root:</p>
     <code>python scripts/seed_demo.py</code>
   </details>
   ```

4. Keep existing error handling for network errors and other failures unchanged

### Implementation Priorities

**Priority 1 (Critical - Do First)**: Layer 1 + Layer 2
- Update README with mandatory setup steps
- Modify backend login endpoint to detect empty DB + demo credentials

**Priority 2 (Recommended - Do After)**: Layer 3
- Enhance frontend error display to show seed_demo.py instruction

**Priority 3 (Nice-to-Have)**: Automation
- Add optional auto-seed in Docker entrypoint or Flask CLI command
- Example: `python scripts/seed_demo.py --auto-on-first-run`
- This is NOT required but improves DX

## Testing Strategy

### Validation Approach

The testing strategy follows a **three-phase approach**:
1. **Exploratory Bug Condition Checking**: Verify bug manifests on unfixed code with empty database
2. **Fix Checking**: Verify fix works correctly when database is empty
3. **Preservation Checking**: Verify normal login flow unchanged when database is seeded

### Exploratory Bug Condition Checking

**Goal**: Reproduce the bug on UNFIXED code, confirm that generic 401 error is displayed when demo credentials used on empty database.

**Test Plan**: 
1. Start with fresh/empty database (delete `data/priomed.db`)
2. Start backend API
3. Attempt login via frontend with "apoteker1" / "demo1234"
4. Observe generic "Username atau password salah" error (current broken behavior)
5. Verify user confusion: error gives no hint about needing to seed database

**Test Cases**:
1. **Empty DB - Demo Credentials**: POST `/api/v1/auth/login` with `{"username": "apoteker1", "password": "demo1234"}` on empty database → expect generic 401 (demonstrates bug)
2. **Empty DB - Invalid Credentials**: POST `/api/v1/auth/login` with `{"username": "fake", "password": "wrong"}` on empty database → expect generic 401 (baseline, should be same as above)
3. **Frontend Display**: Load LoginPage on empty database, attempt login with demo creds, verify error message is generic (demonstrates UX issue)

**Expected Counterexamples (Bug Manifestation)**:
- Backend returns "Username atau password salah" instead of "Akun demo belum diinisialisasi"
- No indication in UI that seed script needs to run
- User has no path forward from error message

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds (empty DB + demo credentials), the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL (username, password) WHERE isBugCondition({username, password}) DO
  GIVEN database is empty (fresh state)
  WHEN POST /api/v1/auth/login with {username, password}
  THEN response status = 401
  AND response.detail contains "seed_demo.py" OR "diinisialisasi"
  AND frontend displays informative error (not generic message)
END FOR
```

**Test Cases**:
1. **Empty DB - apoteker1**: POST login with "apoteker1" / "demo1234" → 401 with seed_demo.py hint
2. **Empty DB - ttk1**: POST login with "ttk1" / "demo1234" → 401 with seed_demo.py hint
3. **Empty DB - koordinator1**: POST login with "koordinator1" / "demo1234" → 401 with seed_demo.py hint
4. **Empty DB - admin**: POST login with "admin" / "admin1234" → 401 with seed_demo.py hint
5. **Frontend Error Display**: Verify LoginPage shows special InlineAlert with setup instruction when error mentions seed_demo.py

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold (seeded DB OR valid non-demo credentials), the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL (username, password) WHERE NOT isBugCondition({username, password}) DO
  GIVEN database is seeded (seed_demo.py run successfully)
  WHEN POST /api/v1/auth/login with valid {username, password}
  THEN response = JWT tokens (access + refresh)
  AND response.status = 200
  AND behavior identical to original function
END FOR
```

**Test Plan**: Run these after database is seeded, verify existing login flow is unchanged.

**Test Cases**:
1. **Valid Seeded Demo User**: POST login with "apoteker1" / "demo1234" after seeding → 200 with JWT tokens
2. **Valid Seeded Different User**: POST login with "ttk1" / "demo1234" after seeding → 200 with JWT tokens
3. **Invalid Password After Seeding**: POST login with "apoteker1" / "wrongpass" after seeding → 401 with generic message (same as before)
4. **Non-Existent User After Seeding**: POST login with "fakename" / "demo1234" after seeding → 401 with generic message (same as before)
5. **Token Refresh After Seeded Login**: Verify token refresh still works after successful login
6. **Frontend Redirect After Seeded Login**: Verify LoginPage redirects to dashboard after successful login with demo credentials

### Unit Tests

- Test `_is_database_empty()` helper:
  - Returns `True` when User table is empty
  - Returns `False` when User table has 1+ active users
  - Returns `True` when User table has only system users (if applicable)

- Test login endpoint error detection:
  - Verify special error message for demo credentials on empty DB
  - Verify generic error message for other failures
  - Verify security: no username enumeration even with improved messages

- Test demo credentials list:
  - Verify all expected demo usernames in DEMO_USERNAMES constant
  - Verify new demo users added to seed_demo.py are also added to detection list

### Property-Based Tests

- **Property**: For any combination of (username, password) and database state:
  - If DB is empty AND (username in DEMO_USERNAMES): special error message
  - If DB is seeded AND (username, password) valid: JWT tokens
  - If DB is seeded AND (username, password) invalid: generic error message
  - Error message never reveals whether username exists (security)

- Generate random database states (empty, partial seed, fully seeded) and verify error consistency

- Test across multiple login attempts to ensure no state leakage

### Integration Tests

1. **Full Setup Flow**:
   - Fresh database → login fails with seed hint → user runs seed_demo.py → login succeeds

2. **Demo Credentials Workflow**:
   - After seeding, each demo user can login and access dashboard

3. **Frontend-Backend Integration**:
   - LoginPage displays seed instruction when error mentions seed_demo.py
   - User can dismiss error and attempt login again

4. **Documentation Accuracy**:
   - README setup steps include seed_demo.py
   - Credentials listed in README match database after seeding
   - Link to setup guide in error message (if implemented) is valid

5. **Multiple Demo Users**:
   - All demo users (apoteker1, ttk1, koordinator1, admin) can login after seeding
   - Each user has correct role and permissions after seed

