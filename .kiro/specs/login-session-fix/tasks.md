# Implementation Plan - Login Session Fix

## Overview

Implementasi bugfix untuk memperbaiki pesan error yang salah saat login gagal. Pengguna melihat "Sesi habis" padahal seharusnya melihat pesan backend yang spesifik seperti "Username atau password salah".

## Tasks

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Invalid Login Credentials Error Message
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **GOAL**: Surface counterexamples that demonstrate the bug exists when attempting login with invalid credentials
  - **Scoped PBT Approach**: Focus on concrete failing cases where `/auth/login` returns 401 with credentials rejection
  - Test implementation details from Bug Condition in design:
    - Simulate `/auth/login` endpoint returning 401 status with backend error message "Username atau password salah"
    - Assert that error message returned to user matches backend response exactly
    - Test both scenarios: invalid username and invalid password
    - Verify that "Sesi habis. Silakan login kembali." message does NOT appear
  - Property assertions should match Expected Behavior Properties from design:
    - P1: Error message is "Username atau password salah" (from backend)
    - P2: Error message is NOT "Sesi habis. Silakan login kembali."
    - P3: No auto-refresh token attempt occurs for `/auth/login` 401 responses
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS with counterexample showing "Sesi habis" message appearing instead of expected backend error (this confirms the bug exists)
  - Document counterexamples found:
    - Invalid password: "Username atau password salah" expected, "Sesi habis. Silakan login kembali." received
    - Invalid username: "Username atau password salah" expected, "Sesi habis. Silakan login kembali." received
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Login Authenticated Endpoints Auto-Refresh Behavior
  - **IMPORTANT**: Follow observation-first methodology - run unfixed code first to observe behavior
  - Observe behavior on UNFIXED code for authenticated endpoints receiving 401:
    - When `/worklist` endpoint returns 401 with valid refresh token available
    - When `/encounters/*` endpoint returns 401 with valid refresh token available  
    - When `/auth/me` endpoint returns 401 with valid refresh token available
    - Observe: auto-refresh token is attempted and request is retried with new token
    - Observe: successful completion after refresh
  - Write property-based tests capturing observed behavior patterns from Preservation Requirements:
    - P1: For any non-login endpoint returning 401, auto-refresh token is attempted
    - P2: For any non-login endpoint returning 401, original request is retried after successful refresh
    - P3: Session timeout behavior (15 minutes) remains unchanged for all authenticated endpoints
    - P4: Network error messages remain unchanged ("Gagal terhubung ke server...")
    - P5: Idle lock functionality (30 minutes) continues to function correctly
  - Property-based testing generates many test cases for stronger preservation guarantees:
    - Generate random authenticated endpoints (exclude `/auth/login`)
    - Test with various 401 response scenarios
    - Verify consistent auto-refresh behavior across all non-login endpoints
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (confirms baseline behavior that must be preserved after fix)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 3. Fix for login session expiration error message bug

  - [x] 3.1 Implement the fix
    - **File**: `web/src/lib/apiClient.ts`
    - **Function**: `apiFetch` (core API call handler)
    - **Changes Required**:
      1. Add path detection logic to identify `/auth/login` endpoint:
         - Extract endpoint path from request parameters
         - Compare against login endpoint path `/auth/login`
      
      2. Update 401 error handling to skip auto-refresh for login endpoint:
         - Check if current request path is `/auth/login`
         - If yes: Skip auto-refresh logic and propagate original backend error message
         - If no: Continue with existing auto-refresh logic
      
      3. Preserve original backend error messages:
         - Extract specific error message from response body (e.g., "Username atau password salah")
         - Return this message to UI instead of generic "Sesi habis. Silakan login kembali."
         - Do NOT override with session expiration message for login failures
      
      4. Consider skipAuth flag in auto-refresh decision:
         - If `skipAuth: true` is set on request, skip auto-refresh for all status codes
         - Login requests typically have skipAuth enabled
      
      5. Maintain backward compatibility:
         - All non-login 401 responses should continue to trigger auto-refresh as before
         - All other status codes should be handled exactly as before
         - Error handling for network failures should be unchanged
    
    - _Bug_Condition: isBugCondition(input) where input.status = 401 AND input.path = '/auth/login' AND autoRefreshTokenTriggered(input)_
    - _Expected_Behavior: expectedBehavior(result) - return original backend error message without session expiration message_
    - _Preservation: Auto-refresh must continue to work for non-login 401s; session timeout, idle lock, and network error handling must remain unchanged_
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 3.2 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Invalid Login Credentials Error Message (FIXED)
    - **IMPORTANT**: Re-run the SAME test from task 1 on the FIXED code - do NOT write a new test
    - The test from task 1 encodes the expected behavior (backend error message should be returned)
    - When this test passes, it confirms the expected behavior is satisfied and bug is fixed
    - Run bug condition exploration test from step 1 on the FIXED code
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed and error message is correct)
    - Verify that:
      - Error message for invalid password is "Username atau password salah" (not "Sesi habis")
      - Error message for invalid username is "Username atau password salah" (not "Sesi habis")
      - No auto-refresh attempt occurs for login 401 responses
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.3 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Login Authenticated Endpoints Auto-Refresh Behavior (PRESERVED)
    - **IMPORTANT**: Re-run the SAME tests from task 2 on the FIXED code - do NOT write new tests
    - Run preservation property tests from step 2 on the FIXED code
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions - auto-refresh still works for non-login endpoints)
    - Verify that:
      - Auto-refresh token is still triggered for non-login endpoints returning 401
      - Session timeout behavior (15 minutes) is unchanged
      - Idle lock functionality (30 minutes) is unchanged
      - Network error messages are unchanged
    - Confirm all tests still pass after fix with no regressions
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 4. Checkpoint - Ensure all tests pass
  - Re-run full test suite to ensure no other tests were affected by the fix
  - Confirm bug condition exploration test passes (bug is fixed)
  - Confirm preservation tests pass (no regressions)
  - Confirm all other existing tests continue to pass
  - Document any issues or edge cases that needed additional handling
  - Mark complete when all tests pass and fix is verified

---

## Testing Summary

### What We're Testing

**Bug Condition Tests (Property 1)**:
- Verifies that when `/auth/login` returns 401 with credentials rejection, the exact backend error message is returned to the user
- Confirms that the misleading "Sesi habis. Silakan login kembali." message does NOT appear
- Tests both invalid username and invalid password scenarios

**Preservation Tests (Property 2)**:
- Verifies that auto-refresh token functionality continues to work for authenticated endpoints
- Confirms that session timeout behavior (15 minutes) is unchanged
- Confirms that idle lock functionality (30 minutes) is unchanged
- Confirms that network error messages remain unchanged
- Ensures no regressions were introduced by the fix

### Running Tests

All tests should be run in the following order:

1. Run bug condition exploration test on UNFIXED code → expect FAILURE (confirms bug exists)
2. Run preservation tests on UNFIXED code → expect PASS (confirms baseline behavior)
3. Implement the fix in `apiClient.ts`
4. Run bug condition exploration test on FIXED code → expect PASS (confirms bug is fixed)
5. Run preservation tests on FIXED code → expect PASS (confirms no regressions)
6. Run full test suite → expect all tests to PASS

---

## References

- **Bug Analysis**: See `bugfix.md` sections 1.1-1.4 for current defective behavior
- **Expected Behavior**: See `bugfix.md` sections 2.1-2.5 for correct behavior specification
- **Preservation Requirements**: See `bugfix.md` sections 3.1-3.4 for unchanged behaviors
- **Design Details**: See `design.md` for bug condition formal specification, root cause analysis, and testing strategy
- **Implementation Target**: `web/src/lib/apiClient.ts` - `apiFetch` function

## Task Dependency Graph

```json
{
  "waves": [
    {
      "wave": 1,
      "tasks": ["1"],
      "description": "Bug Condition Exploration - establish baseline bug"
    },
    {
      "wave": 2,
      "tasks": ["2"],
      "description": "Preservation Tests - document baseline behavior"
    },
    {
      "wave": 3,
      "tasks": ["3"],
      "description": "Implementation - apply fix and verify"
    },
    {
      "wave": 4,
      "tasks": ["4"],
      "description": "Checkpoint - final verification"
    }
  ]
}
```

## Notes

- **PBT Approach**: Both exploration (Property 1) and preservation (Property 2) tests use property-based testing to provide comprehensive coverage and catch edge cases
- **Observation-First**: Preservation tests follow the observation-first methodology - run on unfixed code first to understand actual behavior before writing assertions
- **Test Independence**: Property 1 (Bug Condition) and Property 2 (Preservation) are independent and can be run in any order
- **No Breaking Changes**: All changes are localized to `apiClient.ts` error handling logic with no impact on API contracts or other modules
- **Backward Compatibility**: The fix maintains all existing behavior for non-login endpoints and preserves session management functionality
