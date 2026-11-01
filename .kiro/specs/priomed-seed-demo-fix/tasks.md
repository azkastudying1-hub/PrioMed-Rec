# Implementation Plan — seed_demo.py Path Resolution Fix

## Overview

Tasks ini mengimplementasikan perbaikan untuk path resolution logic di `scripts/seed_demo.py` sehingga script dapat dijalankan langsung dari project root tanpa perlu manual PYTHONPATH configuration.

**Target Goal:** 
```bash
python scripts/seed_demo.py [--reset] [--db-path data/priomed.db]
```
berjalan **dari project root** tanpa `PYTHONPATH=backend` prefix.

**Bug Condition (C):** Script dijalankan dari project root dengan `python scripts/seed_demo.py` tetapi import `from api.db.session import session_scope` gagal karena `api` module tidak ditemukan di Python path.

**Expected Behavior (P):** Dengan path resolution fix, script otomatis menambahkan `backend/` ke `sys.path` berdasarkan lokasi script yang relatif terhadap project root, sehingga semua import `from api.*` berhasil.

**Preservation (¬C):** Semua perilaku existing script (seeding data, database operations, argument parsing) tetap unchanged; hanya path resolution logic yang diperbaiki.

---

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1", "2"] },
    { "wave": 2, "tasks": ["3.1"] },
    { "wave": 3, "tasks": ["3.2", "3.3"] },
    { "wave": 4, "tasks": ["4.1"] },
    { "wave": 5, "tasks": ["5"] }
  ]
}
```

---

## Tasks

- [ ] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - seed_demo.py Path Resolution Failure
  - **CRITICAL**: Jalankan test ini pada kode UNFIXED — failure mengkonfirmasi bug ada
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: Test ini mengkodekan expected behavior — akan memvalidasi fix saat pass setelah implementasi
  - **GOAL**: Surface counterexamples yang mendemonstrasikan bug condition path resolution
  - Buat file `tests/test_seed_demo_exploration.py` dengan test berikut:
    - **Test 1a — Current path resolution logic**: Verifikasi bahwa `sys.path.insert(0, str(Path(__file__).parent.parent))` ada di top of `scripts/seed_demo.py`
    - **Test 1b — Module import failure without PYTHONPATH**: 
      ```python
      import subprocess
      result = subprocess.run(
          ["python", "scripts/seed_demo.py"],
          cwd=project_root,
          capture_output=True,
          text=True,
          env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"}  # Remove PYTHONPATH
      )
      # Expected: returncode != 0 dengan stderr berisi "ModuleNotFoundError: No module named 'api'"
      assert result.returncode != 0, "Script should fail without PYTHONPATH"
      assert "ModuleNotFoundError" in result.stderr or "No module named" in result.stderr
      ```
    - **Test 1c — Path resolution logic accuracy**: Verifikasi bahwa `Path(__file__).parent.parent` menunjuk ke project root dengan benar
      ```python
      script_path = Path("scripts/seed_demo.py")
      resolved_parent = script_path.parent.parent.resolve()
      project_root = Path.cwd().resolve()
      assert resolved_parent == project_root, f"Path mismatch: {resolved_parent} != {project_root}"
      ```
    - **Test 1d — API module not in default path**: Verifikasi bahwa tanpa addition ke sys.path, `api` module tidak dapat diimport
      ```python
      import subprocess
      result = subprocess.run(
          ["python", "-c", "import api.db.session"],
          cwd=project_root,
          capture_output=True,
          text=True,
          env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
      )
      # Expected: returncode != 0 dengan error ModuleNotFoundError
      assert result.returncode != 0
      assert "No module named 'api'" in result.stderr
      ```
    - **Test 1e — backend/api directory exists**: Verifikasi struktur direktori yang diharapkan
      ```python
      backend_api_path = Path("backend/api")
      assert backend_api_path.exists(), f"backend/api directory not found at {backend_api_path}"
      assert (backend_api_path / "main.py").exists(), "backend/api/main.py not found"
      assert (backend_api_path / "db").exists(), "backend/api/db directory not found"
      ```
    - Jalankan test pada kode UNFIXED: 
      ```bash
      python -m pytest tests/test_seed_demo_exploration.py -v
      ```
    - **EXPECTED OUTCOME**: Test 1b dan 1d FAIL (mendemonstrasikan bug bahwa tanpa PYTHONPATH, import gagal); test 1a, 1c, 1e PASS (mengkonfirmasi struktur dan logic sudah ada tetapi tidak cukup)
    - Dokumentasikan counterexample: "Running `python scripts/seed_demo.py` dari project root tanpa PYTHONPATH=backend menghasilkan ModuleNotFoundError karena sys.path.insert hanya menambahkan project root, bukan backend/"
    - Mark task complete saat test ditulis, dijalankan, dan counterexample didokumentasikan
  - _Requirements: 1.1, 1.2_

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing Seed Behavior Unchanged
  - **IMPORTANT**: Follow observation-first methodology — observasi perilaku unfixed code terlebih dahulu, lalu tulis test
  - Buat file `tests/test_seed_demo_preservation.py` dengan test berikut:
    - **Preservation 2a — Database seeding works with PYTHONPATH**:
      ```python
      # Observe: dengan PYTHONPATH=backend, script sukses seed data
      import subprocess
      result = subprocess.run(
          ["python", "scripts/seed_demo.py"],
          cwd=project_root,
          capture_output=True,
          text=True,
          env={**os.environ, "PYTHONPATH": "backend"}
      )
      # Expected: returncode == 0
      assert result.returncode == 0, f"Script failed with PYTHONPATH: {result.stderr}"
      assert "[seed] Selesai" in result.stdout
      # Write test to verify this still works after fix
      ```
    - **Preservation 2b — Seeded data is correct**: 
      ```python
      # Observe: database contains expected demo scenarios S1-S10
      from api.db.session import session_scope as get_session
      from api.db.models import Encounter
      
      with get_session() as session:
          encounters = session.query(Encounter).filter(
              Encounter.patient_id.like("DEMO-S%")
          ).all()
          assert len(encounters) == 10, f"Expected 10 demo encounters, got {len(encounters)}"
          patient_ids = sorted([enc.patient_id for enc in encounters])
          expected = [f"DEMO-S{i:02d}" for i in range(1, 11)]
          assert patient_ids == expected
      ```
    - **Preservation 2c — Database reset flag works**:
      ```python
      # Observe: --reset flag clears demo data and re-seeds
      import subprocess
      result = subprocess.run(
          ["python", "scripts/seed_demo.py", "--reset"],
          cwd=project_root,
          capture_output=True,
          text=True,
          env={**os.environ, "PYTHONPATH": "backend"}
      )
      # Expected: returncode == 0
      assert result.returncode == 0
      assert "[seed] Reset: menghapus data demo lama" in result.stdout or "[seed] Skenario S1" in result.stdout
      ```
    - **Preservation 2d — Command-line arguments preserved**:
      ```python
      # Observe: --db-path argument works
      import subprocess
      result = subprocess.run(
          ["python", "scripts/seed_demo.py", "--db-path", "data/test_seed.db"],
          cwd=project_root,
          capture_output=True,
          text=True,
          env={**os.environ, "PYTHONPATH": "backend"}
      )
      # Expected: returncode == 0
      assert result.returncode == 0
      assert "[seed] Selesai" in result.stdout
      # Cleanup
      Path("data/test_seed.db").unlink(missing_ok=True)
      ```
    - **Preservation 2e — Demo users and accounts created**:
      ```python
      # Observe: Demo user accounts are seeded correctly
      from api.db.session import session_scope as get_session
      from api.db.models import User
      
      with get_session() as session:
          users = session.query(User).filter(User.username.in_([
              "apoteker1", "ttk1", "koordinator1", "admin"
          ])).all()
          assert len(users) == 4, f"Expected 4 demo users, got {len(users)}"
          roles = {u.username: u.role for u in users}
          assert roles["apoteker1"] == "PHARMACIST"
          assert roles["ttk1"] == "TECHNICIAN"
          assert roles["koordinator1"] == "COORDINATOR"
          assert roles["admin"] == "ADMIN"
      ```
    - Jalankan tests pada kode UNFIXED (dengan PYTHONPATH=backend workaround): 
      ```bash
      PYTHONPATH=backend python -m pytest tests/test_seed_demo_preservation.py -v
      ```
    - **EXPECTED OUTCOME**: Semua preservation tests PASS (mengkonfirmasi baseline behavior yang harus dipertahankan dengan atau tanpa fix)
    - Mark task complete saat tests ditulis, dijalankan, dan passing pada unfixed code (dengan PYTHONPATH workaround)
  - _Requirements: 2.1, 2.2, 2.3_

- [ ] 3. Fix path resolution logic in `scripts/seed_demo.py`

  - [ ] 3.1 Improve sys.path setup to add backend/ directory
    - **Current code** (at top of script after imports):
      ```python
      sys.path.insert(0, str(Path(__file__).parent.parent))
      ```
    - **New code** — tambahkan backend/ ke sys.path:
      ```python
      # Determine project root and add backend/ to Python path
      # This allows script to be run from any directory without PYTHONPATH=backend
      script_dir = Path(__file__).parent  # scripts/
      project_root = script_dir.parent    # project_root/
      backend_dir = project_root / "backend"
      
      # Add project root and backend/ to sys.path
      if str(project_root) not in sys.path:
          sys.path.insert(0, str(project_root))
      if str(backend_dir) not in sys.path:
          sys.path.insert(0, str(backend_dir))
      
      # Verify backend/api exists
      if not (backend_dir / "api").exists():
          raise RuntimeError(
              f"Error: backend/api not found at {backend_dir / 'api'}. "
              f"Please run this script from project root or ensure backend/ directory exists."
          )
      ```
    - **Rationale:** Menambahkan explicit `backend/` ke sys.path memastikan `from api.main import app` dapat menemukan module `api` dari mana pun script dijalankan. Validasi direktori memberikan error message yang jelas jika struktur project tidak sesuai.
    - **Placement:** Ubah blok sys.path di baris setelah block `from __future__ import annotations` dan sebelum `import argparse`
    - Verifikasi: Script dapat dijalankan dengan `python scripts/seed_demo.py` dari project root tanpa PYTHONPATH
    - Acceptance criteria: 
      - Script tidak lagi memerlukan `PYTHONPATH=backend` prefix
      - Error message jelas jika backend/ directory tidak ada
      - Path resolution logic mengambil dirname dari __file__ untuk portability (bekerja dari mana saja di project tree)
    - _Bug_Condition: isBugCondition — script dijalankan dari project root tanpa PYTHONPATH; `sys.path` hanya berisi project_root bukan backend/_
    - _Expected_Behavior: Script menambahkan both project_root dan backend/ ke sys.path; import `from api.db.session` berhasil_
    - _Preservation: Argument parsing, database seeding logic, user account creation tetap unchanged (2.2, 2.3)_
    - _Requirements: 1.1, 1.2, 2.1, 2.2_

  - [ ] 3.2 Verify no other hard-coded paths in script
    - Cari dan verifikasi bahwa tidak ada hard-coded absolute paths atau path assumptions lainnya
    - Periksa: `Path("data/priomed.db")` adalah relative path yang benar (akan diresolve terhadap cwd)
    - Periksa: Semua file references menggunakan relative paths (tidak ada `/app/`, `/home/`, hardcoded user directories)
    - Acceptance criteria: `grep -E "^(Path\(|open\()" scripts/seed_demo.py` menunjukkan semua paths adalah relative atau dynamically determined
    - _Requirements: 1.1_

  - [ ] 3.3 Add script documentation for running from any directory
    - Tambahkan docstring di awal script (sudah ada) untuk menjelaskan path resolution behavior:
      ```python
      """
      scripts/seed_demo.py
      ---------------------
      Seed deterministik skenario demo S1–S10 (B-115).

      **IMPORTANT**: Script ini dapat dijalankan dari project root WITHOUT PYTHONPATH configuration:
          python scripts/seed_demo.py [--reset] [--db-path data/priomed.db]

      Path resolution:
      - Script otomatis mendeteksi project root dari lokasi file (__file__).
      - Backend directory ditambahkan ke sys.path agar import `from api.*` berhasil.
      - Dapat dijalankan dari:
        - Project root: `python scripts/seed_demo.py`
        - Subdirectory: `cd backend && python ../scripts/seed_demo.py`
        - Dengan full path: `python /full/path/to/scripts/seed_demo.py`
      
      Database:
      - Default db path: `data/priomed.db` (relative to project root)
      - Custom db path: `python scripts/seed_demo.py --db-path /custom/path.db`
      
      Data reset:
      - First run: seed semua demo data dan user accounts
      - Subsequent runs: seed ulang demo encounters (user accounts dipertahankan kecuali demo user direset)
      - Reset dengan flag: `python scripts/seed_demo.py --reset` (menghapus semua demo data dan ulang seed)

      Skenario:
        S1  — Pasien high-risk, banyak diskrepansi omisi, high-alert (warfarin) → tier HIGH
        ...
        S10 — TTK submit BPMH → Apoteker telaah → APPROVE → Audit trail hash-chain valid

      STATUS: Semua data adalah data SINTETIS (S9 dari prinsip keselamatan).
      JANGAN masukkan data pasien nyata.
      """
      ```
    - Acceptance criteria: Docstring di-update dengan informasi path resolution
    - _Requirements: 2.1, 2.2_

- [ ] 4. Verify bug condition exploration test now passes
  - **Property 1: Expected Behavior** - seed_demo.py Runnable Without PYTHONPATH
  - **IMPORTANT**: Re-run test yang SAMA dari task 1 — JANGAN tulis test baru
  - Jalankan: `python -m pytest tests/test_seed_demo_exploration.py -v`
  - **EXPECTED OUTCOME**: 
    - Test 1b dan 1d kini PASS karena script dapat dijalankan tanpa PYTHONPATH
    - Test 1a, 1c, 1e tetap PASS (struktur unchanged)
    - Semua tests menunjukkan bahwa path resolution logic berhasil
  - Verifikasi masing-masing:
    - `python scripts/seed_demo.py` dari project root → returncode 0 ✓
    - `python -c "from api.db.session import session_scope"` berjalan tanpa error ✓ (dijalankan oleh script)
    - Path resolution logic dari __file__ menunjuk ke backend/ ✓
  - _Requirements: 2.1, 2.2_

- [ ] 5. Verify preservation tests still pass
  - **Property 2: Preservation** - No Regressions After Fix
  - **IMPORTANT**: Re-run test yang SAMA dari task 2 — JANGAN tulis test baru
  - Jalankan: `python -m pytest tests/test_seed_demo_preservation.py -v` (tanpa PYTHONPATH=backend prefix sekalipun, karena fix sekarang mengatasinya)
  - **EXPECTED OUTCOME**: Semua preservation tests masih PASS (mengkonfirmasi tidak ada regresi)
  - Verifikasi setiap requirement:
    - `python scripts/seed_demo.py` dari project root berhasil seed data ✓ (2.1)
    - Database berisi 10 demo encounters S1-S10 ✓ (2.2)
    - `python scripts/seed_demo.py --reset` berhasil reset dan re-seed ✓ (2.2)
    - `python scripts/seed_demo.py --db-path custom.db` menerima custom database path ✓ (2.3)
    - Demo users (apoteker1, ttk1, koordinator1, admin) seeding masih bekerja ✓ (2.1, 2.2, 2.3)
  - Konfirmasi tidak ada regresi setelah fix diterapkan

---

## Fix Summary

### What's Fixed

1. **Path Resolution Logic**: Script sekarang menggunakan `__file__` untuk mendeteksi lokasi script secara dinamis, lalu menambahkan `backend/` directory ke sys.path. Ini memungkinkan script berjalan dari project root tanpa PYTHONPATH configuration.

2. **Error Handling**: Jika `backend/api` tidak ditemukan, script memberikan error message yang jelas dengan saran untuk memastikan struktur project benar.

3. **Documentation**: Docstring dan inline comments menjelaskan path resolution behavior untuk memudahkan maintenance dan debugging.

### What's NOT Changed

- Semua database seeding logic tetap sama
- Argument parsing (`--reset`, `--db-path`) tetap sama
- Skenario demo S1-S10 tetap sama
- User account seeding tetap sama
- Alembic migration execution tetap sama

---

## Verification Checklist

Before marking complete:

- [ ] Bug condition exploration test written and run on unfixed code
- [ ] Counterexample documented: "Running without PYTHONPATH fails with ModuleNotFoundError"
- [ ] Preservation tests written and run on unfixed code (with PYTHONPATH workaround)
- [ ] Fix implemented: sys.path.insert calls updated with dynamic path resolution
- [ ] Script runs successfully: `python scripts/seed_demo.py` from project root
- [ ] Error handling verified: Script fails gracefully if backend/ missing
- [ ] All exploration tests re-run and PASS
- [ ] All preservation tests re-run and PASS
- [ ] No regressions: seeding, reset, custom db-path all work

---

## Notes

- Task 1 dan 2 adalah **Property-Based Tests** yang harus ditulis SEBELUM fix diterapkan
- Task 1 (Bug Condition) — assertion mengkonfirmasi bug condition exist pada unfixed code
- Task 2 (Preservation) — diharapkan PASS pada kode unfixed (dengan PYTHONPATH workaround) sebagai baseline
- Task 3 adalah implementasi fix dengan path resolution improvement
- Task 4-5 menggunakan test yang SAMA dari task 1-2 untuk verifikasi setelah fix
- Fix ini adalah **minimal change** — hanya path resolution logic yang berubah
- Path resolution menggunakan `Path(__file__).parent.parent` untuk portability — bekerja dari project root atau subdirectory
- Script sudah memiliki docstring; improvement documentation adalah penambahan di bagian yang ada, bukan rewrite

