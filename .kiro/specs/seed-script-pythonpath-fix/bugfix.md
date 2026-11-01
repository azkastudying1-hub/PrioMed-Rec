# Bugfix Requirements Document

## Introduction

The `scripts/seed_demo.py` script fails with `ModuleNotFoundError: No module named 'api'` when run from the project root using the standard command `python scripts/seed_demo.py`. This occurs because the script cannot locate the `api` package which is located at `backend/api/`. Users must currently work around this by manually setting `PYTHONPATH=backend`, which creates friction for first-time users attempting to seed the demonstration database.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a user runs `python scripts/seed_demo.py` from the project root directory THEN the script fails with `ModuleNotFoundError: No module named 'api'`

1.2 WHEN the script attempts to import modules from the `api` package (e.g., `from api.db.session import session_scope`) THEN the import fails because `backend/api/` is not in the Python module search path

### Expected Behavior (Correct)

2.1 WHEN a user runs `python scripts/seed_demo.py` from the project root directory THEN the script SHALL successfully import all required modules from the `api` package without requiring manual PYTHONPATH configuration

2.2 WHEN the script initializes THEN it SHALL automatically resolve the correct Python path to locate the `backend/api/` package

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a user runs the script with `--reset` flag THEN the script SHALL CONTINUE TO delete demo data and reseed as before

3.2 WHEN a user runs the script with `--db-path` parameter THEN the script SHALL CONTINUE TO use the specified database path

3.3 WHEN the script executes the seeding logic THEN it SHALL CONTINUE TO create all demo scenarios S1–S10 with correct data and relationships

3.4 WHEN database operations complete THEN the script SHALL CONTINUE TO display account credentials and completion message as before

3.5 WHEN a user runs the script with `PYTHONPATH=backend python scripts/seed_demo.py` (the current workaround) THEN it SHALL CONTINUE TO work without errors
