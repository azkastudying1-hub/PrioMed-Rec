# seed_demo.py PYTHONPATH Fix — Design Document

## Overview

The `scripts/seed_demo.py` script requires manual PYTHONPATH configuration to run successfully, creating friction for developers and CI/CD pipelines. This design proposes embedding automatic path resolution directly into the script, enabling it to be executed naturally from the project root using `python scripts/seed_demo.py` without requiring environment variable setup. The fix improves developer experience by eliminating a non-obvious prerequisite while maintaining backward compatibility with the existing workaround.

## Glossary

- **Bug_Condition (C)**: User attempts to run the seed script from project root without setting PYTHONPATH, causing module import failures
- **Property (P)**: Script automatically resolves and configures the Python path to find backend modules
- **Preservation**: Existing functionality (data seeding, CLI arguments, database operations, output messages) remains unchanged
- **seed_demo.py**: The demo data seeding script located at `scripts/seed_demo.py` that populates the database with test scenarios S1–S10
- **api package**: The backend application code located at `backend/api/` containing database models, session management, and business logic
- **PYTHONPATH**: Python environment variable that controls the module search path; typically requires `backend` to locate the `api` package
- **Script execution context**: The working directory from which the user runs the Python script (e.g., project root `d:\Hacktiv8\priomed-rec\`)

## Bug Details

### Bug Condition

The bug manifests when a developer attempts to run the seed script directly from the project root using the intuitive command `python scripts/seed_demo.py`. The script then imports modules from the `api` package (e.g., `from api.db.session import session_scope`), but Python cannot locate the `api` package because the `backend/` directory is not in the module search path. The script either fails silently or the `__main__` block reaches the point where imports are attempted, causing a `ModuleNotFoundError`.

**Formal Specification:**
```
FUNCTION isBugCondition(executionContext)
  INPUT: executionContext = {
    workingDirectory: string,
    pythonPath: string[],
    scriptPath: string,
    attemptedImports: string[]
  }
  OUTPUT: boolean
  
  RETURN workingDirectory == projectRoot
         AND "backend" NOT IN pythonPath
         AND scriptPath == "scripts/seed_demo.py"
         AND ANY import IN attemptedImports WHERE import STARTSWITH "from api"
         AND moduleName "api" NOT FOUND in pythonPath
END FUNCTION
```

### Examples

**Example 1: Direct execution from project root**
- Command: `cd d:\Hacktiv8\priomed-rec && python scripts\seed_demo.py`
- Expected: Demo data seeded successfully
- Actual: `ModuleNotFoundError: No module named 'api'` at line `from api.db.session import session_scope`

**Example 2: Direct execution from project root with reset flag**
- Command: `cd d:\Hacktiv8\priomed-rec && python scripts\seed_demo.py --reset`
- Expected: Existing demo data deleted, then S1–S10 scenarios reseeded
- Actual: `ModuleNotFoundError: No module named 'api'`

**Example 3: Current workaround (should continue to work)**
- Command: `cd d:\Hacktiv8\priomed-rec && PYTHONPATH=backend python scripts\seed_demo.py`
- Expected: Works correctly
- Actual: Works correctly (preservation requirement)

**Example 4: Edge case — execution from nested directory**
- Command: `cd d:\Hacktiv8\priomed-rec\scripts && python seed_demo.py`
- Expected: Script should detect it is being run from a subdirectory and resolve the path correctly
- Actual: May fail unless path resolution is robust

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- The `--reset` flag continues to delete demo data and reseed all scenarios
- The `--db-path` parameter continues to override the default database path
- All demo scenarios S1–S10 are created with identical structure and relationships
- User credentials and account information are created exactly as before
- Console output messages (completion status, account credentials) remain unchanged
- SLA configuration defaults are seeded as before
- All database relationships and foreign keys work identically

**Scope:**
All inputs that do NOT involve the Python module import path should be completely unaffected by this fix. This includes:
- Database seeding logic and data insertion
- Command-line argument parsing
- CLI flag handling
- Environment variable handling (e.g., DB_PATH)
- All SQLAlchemy models and database queries
- Output message formatting

## Hypothesized Root Cause

Based on the bug description, the most likely issues are:

1. **Missing Path Resolution at Script Start**: The script uses `sys.path.insert(0, str(Path(__file__).parent.parent))` to add the project root, but this assumes the script is invoked directly (not as a module) and the working directory is not the determining factor. When Python initially loads the script, it adds only the current working directory and standard library paths, not the script's directory.

2. **Incorrect Relative Path Calculation**: The line `sys.path.insert(0, str(Path(__file__).parent.parent))` calculates relative to the script file itself, which resolves to the project root. However, if the script is invoked from a different working directory, this path may already be in sys.path under a different form, or the calculation might not account for all import scenarios.

3. **Import Timing Issues**: The imports at the top of the file (lines with `from api.db.session import...`) occur inside functions, but the __main__ block also imports these modules. If any imports occur before the path modification, they fail before the fix can take effect.

4. **Python Execution Environment**: When running `python scripts/seed_demo.py`, the initial sys.path includes the directory containing the script and the current working directory. The path calculation may not account for symlinks, Windows path separators, or other environment-specific edge cases.

## Correctness Properties

Property 1: Bug Condition - Automatic PYTHONPATH Resolution

_For any_ execution where the script is invoked from project root (or any subdirectory) without explicit PYTHONPATH configuration, and the script attempts to import modules from the `api` package, the fixed seed_demo.py script SHALL automatically resolve the backend directory path and add it to sys.path BEFORE any module imports are attempted.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation - Existing Workaround and Functionality

_For any_ execution where the bug condition does NOT hold (e.g., PYTHONPATH is already set, script runs with explicit path exports, or all imports succeed), the fixed script SHALL produce exactly the same result as the original script, preserving all existing database seeding logic, CLI argument handling, and output messages.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct, the following changes are required:

**File**: `scripts/seed_demo.py`

**Function**: `__main__` block (top of file, before any imports from `api`)

**Specific Changes**:

1. **Robust Path Resolution at Module Load**: Add path resolution code that executes immediately when the script is imported/loaded, before any conditional imports. This ensures the path is always available.

   - Use `Path(__file__).resolve()` instead of `Path(__file__)` to handle symlinks and relative paths correctly
   - Calculate the project root as `Path(__file__).resolve().parent.parent` (scripts/../..)
   - Verify the backend directory exists before adding to sys.path
   - Add backend directory to sys.path.insert(0, ...) at the very top, after imports but before any relative imports

2. **Path Resolution with Fallback**: If running from a subdirectory or via module execution, implement fallback logic that can still locate the backend directory.

   - Check if backend exists at the calculated path
   - If not found, walk up the directory tree searching for a `backend/api` directory structure
   - If still not found, raise a clear error message indicating the script must be run from within the project

3. **Validation and Error Messaging**: Add clear error messages when path resolution fails, helping developers understand what went wrong.

   - Log the resolved Python paths for debugging
   - Verify that `api` package can be imported after path modification
   - Provide guidance if the backend path cannot be found

4. **Platform Compatibility**: Ensure the path resolution works on Windows (backslashes), Linux (forward slashes), and macOS.

   - Use `pathlib.Path` consistently (already present in code)
   - Avoid string-based path manipulation

5. **Minimal Code Addition**: Keep the changes focused and minimal to avoid introducing new bugs or altering existing functionality.

   - Add only 5-10 lines of robust path resolution code
   - No changes to function signatures or logic
   - No changes to import statements or database operations

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on the unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that simulate running the script from the project root without PYTHONPATH set. Capture the error and analyze the module search path (sys.path) at the point of failure. Run these tests on the UNFIXED code to observe failures and understand the root cause.

**Test Cases**:
1. **Direct Execution from Project Root**: Run `python scripts/seed_demo.py --help` from project root without PYTHONPATH set (will fail on unfixed code showing the import error before help text is displayed)
2. **Execution with --db-path Override**: Run `python scripts/seed_demo.py --db-path data/test.db` without PYTHONPATH (will fail on unfixed code)
3. **Execution with --reset Flag**: Run `python scripts/seed_demo.py --reset` without PYTHONPATH (will fail on unfixed code)
4. **Execution from Subdirectory**: Run from `scripts/` directory without PYTHONPATH (may fail on unfixed code depending on current implementation)

**Expected Counterexamples**:
- `ModuleNotFoundError: No module named 'api'` on line attempting to import from api package
- sys.path does not contain the backend directory or project root in a position where api package is found
- Possible causes: path calculation assumes current working directory is project root, path calculation doesn't account for script invocation method, backend directory path is calculated incorrectly

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL execution WHERE isBugCondition(execution) DO
  result := seed_demo_fixed(execution)
  ASSERT scriptExecutedSuccessfully(result)
  ASSERT pythonPathIncludesBackend(result)
  ASSERT expectedBehavior(result)
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL execution WHERE NOT isBugCondition(execution) DO
  ASSERT seed_demo_original(execution) = seed_demo_fixed(execution)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain (different working directories, different PYTHONPATH settings, different CLI arguments)
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: First observe behavior on UNFIXED code when PYTHONPATH is set (to establish baseline), then write property-based tests capturing that behavior and verifying it is preserved after the fix.

**Test Cases**:
1. **PYTHONPATH Already Set Preservation**: With PYTHONPATH=backend, verify script output and database state match baseline on unfixed code
2. **CLI Argument Handling Preservation**: Verify `--reset`, `--db-path`, `--help` continue to work identically after fix
3. **Database Seeding Preservation**: Verify all S1–S10 scenarios are created with identical structure (same fields, same values, same relationships)
4. **Output Message Preservation**: Verify console output messages, account credentials display, and completion status messages are identical
5. **Environment Variable Handling Preservation**: Verify DB_PATH environment variable continues to work when set

### Unit Tests

- Test path resolution logic in isolation (verify backend directory is correctly located from various execution contexts)
- Test that `api` module can be imported after path resolution
- Test error handling when backend directory cannot be found
- Test that seed() function executes successfully after path is resolved
- Test CLI argument parsing (--reset, --db-path, --help)

### Property-Based Tests

- Generate random working directories within the project and verify script can find backend from any of them
- Generate random combinations of CLI arguments and verify behavior is unchanged from baseline
- Verify that database state is identical whether script is run with or without explicit PYTHONPATH
- Test that output messages are deterministic and match baseline exactly

### Integration Tests

- Run seed_demo.py from project root without PYTHONPATH, verify database is populated with S1–S10 scenarios
- Run with --reset flag, verify old data is deleted and new data is reseeded
- Run from subdirectories (scripts/, data/, etc.) and verify it still works
- Run multiple times in sequence and verify idempotent behavior (second run without --reset preserves data)
- Verify that demo user accounts can authenticate with provided credentials
- Verify that all demo encounters contain expected data relationships

## Implementation Approach

The fix should be minimal and focused. The recommended approach is **Option 1: Modify script for auto-detect and set PYTHONPATH** because:

1. **Best Developer Experience**: No wrapper scripts or documentation needed; users get intuitive behavior
2. **No Dependencies**: Uses only Python standard library (pathlib, sys)
3. **Portable**: Works on Windows, Linux, and macOS without modification
4. **Maintainable**: All path logic is in one place within the script
5. **Backward Compatible**: Existing workarounds continue to work
6. **CI/CD Friendly**: Works in Docker, GitHub Actions, and local development without configuration changes

The implementation should:
- Add robust path resolution at the very top of the script (after sys import, before any api imports)
- Calculate the backend directory path relative to the script file
- Implement fallback logic for edge cases
- Provide clear error messages if path resolution fails
- Not modify any existing function signatures or logic

This approach solves the bug at its source while maintaining complete backward compatibility and requiring zero changes to CI/CD pipelines or documentation.
