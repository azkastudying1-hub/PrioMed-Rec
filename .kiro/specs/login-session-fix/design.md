# Login Session Fix Bugfix Design

## Overview

This bugfix addresses an incorrect error message when users attempt to log in with invalid credentials. Instead of receiving the specific "Username atau password salah" message from the backend, users see the misleading "Sesi habis. Silakan login kembali." message. The issue stems from the auto-refresh token logic in `apiClient.ts` incorrectly triggering for `/auth/login` endpoint 401 responses, attempting to refresh a non-existent session.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug - when `/auth/login` endpoint returns 401 status
- **Property (P)**: The desired behavior when login fails - display backend error message, not session expiration message
- **Preservation**: Existing auto-refresh token functionality for authenticated endpoints, session timeout behavior, and idle lock functionality
- **apiFetch**: The core function in `apiClient.ts` that handles all API calls with auto-refresh logic
- **loginApi**: The function that calls `/auth/login` endpoint in `apiClient.ts`
- **refreshAccessToken**: The function in `auth.ts` that attempts to refresh expired access tokens

## Bug Details

### Bug Condition

The bug manifests when a user attempts to log in with invalid credentials (wrong username or password). The `/auth/login` endpoint returns 401 status, but the `apiFetch` function incorrectly triggers the auto-refresh token logic instead of returning the backend's specific error message.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type ApiResponse
  OUTPUT: boolean
  
  RETURN input.status = 401 
         AND input.path = '/auth/login'
         AND autoRefreshTokenTriggered(input)
END FUNCTION
```

### Examples

- **Example 1 (Invalid Password)**: User enters "apt-01" with password "wrongpass"
  - Expected: "Username atau password salah" (from backend)
  - Actual: "Sesi habis. Silakan login kembali." (incorrect)

- **Example 2 (Invalid Username)**: User enters "nonexistent" with password "demo1234"
  - Expected: "Username atau password salah" (from backend)
  - Actual: "Sesi habis. Silakan login kembali." (incorrect)

- **Example 3 (Valid Login)**: User enters "apt-01" with password "demo1234"
  - Expected: Successful login, redirect to dashboard
  - Actual: Successful login (correct)

- **Example 4 (Expired Session)**: Already logged-in user's session expires
  - Expected: "Sesi habis. Silakan login kembali." (correct)
  - Actual: "Sesi habis. Silakan login kembali." (correct)

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Auto-refresh token logic must continue to work for authenticated endpoints (non-login)
- Session timeout after 15 minutes (JWT_ACCESS_EXPIRE_MINUTES) must remain unchanged
- Idle lock after 30 minutes of inactivity must continue to function
- Network error handling must continue to display "Gagal terhubung ke server. Periksa koneksi Anda."
- Token refresh for expired sessions must continue to work automatically

**Scope:**
All API calls except `/auth/login` should continue to use the auto-refresh logic when receiving 401 status. This includes:
- `/auth/me` endpoint calls
- `/worklist` endpoint calls  
- `/encounters/*` endpoint calls
- `/audit/*` endpoint calls
- `/health` endpoint calls

## Hypothesized Root Cause

Based on the bug description and code analysis, the most likely issues are:

1. **Missing Path Check in Auto-Refresh**: The `apiFetch` function doesn't check if the 401 response is from the `/auth/login` endpoint before attempting token refresh
   - Current logic: Any 401 triggers refresh attempt
   - Correct logic: Only non-login 401s should trigger refresh

2. **Incorrect SkipAuth Handling**: The `skipAuth` option may not be properly considered in the auto-refresh decision
   - Login calls use `skipAuth: true`, but this doesn't affect the 401 handling logic
   - The auto-refresh logic should check both path and skipAuth flag

3. **Hardcoded Error Message**: When refresh fails, a hardcoded "Sesi habis. Silakan login kembali." message is thrown instead of propagating the original backend error
   - This message is appropriate for expired sessions, not login failures

## Correctness Properties

Property 1: Bug Condition - Login Error Message Accuracy

_For any_ API response where status is 401 AND path is `/auth/login`, the fixed `apiFetch` function SHALL propagate the original backend error message (e.g., "Username atau password salah") without attempting token refresh or returning "Sesi habis. Silakan login kembali."

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation - Auto-Refresh Token Functionality

_For any_ API response where status is 401 AND path is NOT `/auth/login`, the fixed `apiFetch` function SHALL produce exactly the same behavior as the original function, preserving all existing auto-refresh token functionality for authenticated endpoints.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `web/src/lib/apiClient.ts`

**Function**: `apiFetch`

**Specific Changes**:
1. **Path Detection Logic**: Add check to identify `/auth/login` endpoint calls
   - Extract path from function parameters
   - Compare against known login endpoint path

2. **Auto-Refresh Condition Update**: Modify 401 handling logic
   - Only attempt auto-refresh if path is NOT `/auth/login`
   - Skip refresh and propagate original error for login 401s

3. **Error Message Propagation**: Ensure original backend error is preserved
   - Extract error message from response body before refresh attempt
   - Throw specific login error instead of generic session expiration message

4. **SkipAuth Integration**: Consider `skipAuth` flag in auto-refresh decision
   - If `skipAuth: true`, skip auto-refresh entirely for 401 responses

5. **Backward Compatibility**: Maintain existing behavior for all other endpoints
   - Non-login 401s should continue auto-refresh as before
   - All other status codes should be handled unchanged

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that simulate login API calls with invalid credentials and assert that the error message matches the backend response. Run these tests on the UNFIXED code to observe failures and understand the root cause.

**Test Cases**:
1. **Invalid Password Test**: Simulate login with correct username but wrong password (will fail on unfixed code)
2. **Invalid Username Test**: Simulate login with non-existent username (will fail on unfixed code)
3. **Valid Login Test**: Simulate successful login (should pass on unfixed code)
4. **Expired Session Test**: Simulate 401 on authenticated endpoint (should pass on unfixed code)

**Expected Counterexamples**:
- Tests 1 and 2 will receive "Sesi habis. Silakan login kembali." instead of "Username atau password salah"
- Possible causes: missing path check, incorrect skipAuth handling, hardcoded error message

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := apiFetch_fixed(input)
  ASSERT result.error_message = original_backend_error_message
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT apiFetch_original(input) = apiFetch_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for authenticated API calls, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Auto-Refresh Preservation**: Verify token refresh still works for expired sessions on non-login endpoints
2. **Network Error Preservation**: Verify network errors still display correct message
3. **Session Timeout Preservation**: Verify session still expires after 15 minutes
4. **Idle Lock Preservation**: Verify idle lock still activates after 30 minutes

### Unit Tests

- Test login API with various credential combinations (valid, invalid username, invalid password)
- Test 401 handling for different endpoints (login vs non-login)
- Test error message propagation from backend
- Test skipAuth flag behavior

### Property-Based Tests

- Generate random API paths and status codes to verify auto-refresh logic
- Generate random error messages to ensure proper propagation
- Test that all non-login 401s continue to trigger auto-refresh across many scenarios
- Test that login 401s never trigger auto-refresh across many scenarios

### Integration Tests

- Test full login flow with invalid credentials in UI
- Test session expiration and auto-refresh in authenticated flows
- Test that idle lock functionality remains intact after fix
- Test that all existing API integrations continue to work correctly