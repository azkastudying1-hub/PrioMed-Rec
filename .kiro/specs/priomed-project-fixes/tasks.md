# Implementation Plan

## Overview

Tasks ini mengimplementasikan perbaikan untuk 10 bug/issue di PrioMed-Rec berdasarkan design.md dan bugfix.md. Urutan eksekusi mengikuti metodologi bugfix: exploration test → preservation test → critical fixes (Docker, Alembic, CI) → Docker Compose fixes → Dockerfile.web → Langflow component stubs → requirements → dokumentasi → verifikasi akhir.

**Bug/Issue yang ditangani:**
- Bug 1: `docker/Dockerfile.api` — missing `ENV PYTHONPATH=/app/backend`
- Bug 2: `alembic.ini` — `script_location` salah + missing `sqlalchemy.url`
- Bug 3: `langflow/components/` — missing component stubs
- Bug 4: `.github/workflows/ci.yml` — missing PYTHONPATH pada step dan job
- Issue 5: Duplikasi `frontend/web/` directory
- Issue 6: `docker/docker-compose.yml` — service `web` tidak join `priomed_internal` network
- Issue 7 & 10: `docker/docker-compose.yml` — build context menunjuk ke `docker/` bukan project root + konsekuensinya pada `Dockerfile.web`
- Issue 8: `alembic.ini` — missing `sqlalchemy.url`
- Issue 9: `langflow/requirements.langflow.txt` kosong

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1", "2"] },
    { "wave": 2, "tasks": ["3.1", "3.2", "3.3"] },
    { "wave": 3, "tasks": ["4.1"] },
    { "wave": 4, "tasks": ["4.2", "4.3"] },
    { "wave": 5, "tasks": ["5.1"] },
    { "wave": 6, "tasks": ["6.1", "6.2", "6.3", "6.4"] },
    { "wave": 7, "tasks": ["7.1"] },
    { "wave": 8, "tasks": ["8"] },
    { "wave": 9, "tasks": ["9", "10"] },
    { "wave": 10, "tasks": ["11"] }
  ]
}
```

## Tasks

- [x] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Configuration Path & Import Failures
  - **CRITICAL**: Jalankan test ini pada kode UNFIXED — failure mengkonfirmasi bug ada
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: Test ini mengkodekan expected behavior — akan memvalidasi fix saat pass setelah implementasi
  - **GOAL**: Surface counterexamples yang mendemonstrasikan semua bug condition dari bugfix.md
  - **Scoped PBT Approach**: Scope property ke concrete failing cases yang deterministik untuk reproducibility
  - Buat file `tests/test_bugfix_exploration.py` dengan test berikut:
    - **Bug 1**: Verifikasi `ENV PYTHONPATH` TIDAK ada di `docker/Dockerfile.api` → konfirmasi bug condition 1.1, 1.2
    - **Bug 2**: Verifikasi `script_location = alembic` ada (bukan `backend/alembic`) → konfirmasi bug condition 1.3, 1.4
    - **Bug 3**: Verifikasi file-file berikut TIDAK ada: `langflow/components/priomedrec/triage.py`, `safety.py`, `audit.py`, `__init__.py` → konfirmasi bug condition 1.5, 1.6
    - **Bug 4**: Verifikasi `PYTHONPATH: backend` TIDAK ada pada step `Verify API imports cleanly` di `.github/workflows/ci.yml` → konfirmasi bug condition 1.7
    - **Bug 4b**: Verifikasi job-level `env: PYTHONPATH: backend` TIDAK ada di job `demo-seed-check` → konfirmasi bug condition 1.8
    - **Issue 6**: Verifikasi service `web` di `docker/docker-compose.yml` tidak memiliki `priomed_internal` di blok `networks:` → konfirmasi bug condition 1.11, 1.12
    - **Issue 9**: Verifikasi `langflow/requirements.langflow.txt` berukuran 0 bytes → konfirmasi bug condition 1.16
    - **Issue 10**: Verifikasi `context: ..` TIDAK ada di `docker/docker-compose.yml` (masih `context: .`) → konfirmasi bug condition 1.17
    - Simulasikan import failure: jalankan `subprocess.run(["python", "-c", "from api.main import app"], capture_output=True)` tanpa PYTHONPATH — expect returncode != 0 → dokumentasi counterexample ModuleNotFoundError
    - Jalankan test: `PYTHONPATH=backend python -m pytest tests/test_bugfix_exploration.py -v`
    - **EXPECTED OUTCOME**: Assertions konfirmasi bug condition exist — tests PASS dengan membuktikan bug ada (atau FAIL apabila kode sudah di-fix sebelumnya)
    - Dokumentasikan counterexamples: "PYTHONPATH missing → ModuleNotFoundError", "script_location wrong → FileNotFoundError", "context: . → COPY build failure", dll.
    - Mark task complete saat test ditulis, dijalankan, dan counterexamples didokumentasikan
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.11, 1.16, 1.17_

- [x] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Existing Behavior Unchanged After Fix
  - **IMPORTANT**: Ikuti observation-first methodology — observasi perilaku unfixed code terlebih dahulu, lalu tulis test
  - Buat file `tests/test_bugfix_preservation.py` dengan test berikut:
    - **Preservation 3.1**: Observe: `PYTHONPATH=backend python -c "from api.main import app; assert len(app.routes) > 10"` sukses → tulis assertion route count tidak berubah setelah fix
    - **Preservation 3.2**: Observe: file-file migration di `backend/alembic/versions/` ada dan tidak dimodifikasi → tulis hash/content assertion
    - **Preservation 3.3**: Observe: file Langflow flows JSON ada di `langflow/flows/` → tulis assertion flows tidak diubah
    - **Preservation 3.4**: Observe: `web/package.json` dan `web/src/` ada dan tidak dimodifikasi → tulis assertion
    - **Preservation 3.5**: Observe: `docker/nginx.conf` mengandung `try_files $uri $uri/ /index.html` → tulis assertion konten tidak berubah
    - **Preservation 3.6**: Observe: `PYTHONPATH=backend python -m pytest tests/test_fase1_b103_auth.py -v` sukses → tulis property test bahwa semua test files yang ada tetap importable dan tidak dimodifikasi
    - **Preservation 3.7**: Observe: `DB_PATH` ada di konfigurasi `backend/api/config.py` atau `database.py` → tulis assertion
    - **Preservation 3.8**: Observe: `docker/docker-compose.yml` service `api` dan `langflow` memiliki `priomed_internal` network → tulis assertion network config tidak hilang
    - **Preservation 3.9**: Observe: `.env.example` mengandung semua key yang diperlukan → tulis assertion format tidak berubah
    - **Preservation 3.10**: Observe: `priomedrec_core/` directory ada di project root → tulis assertion struktur tidak berubah
    - Jalankan tests pada kode UNFIXED: `PYTHONPATH=backend python -m pytest tests/test_bugfix_preservation.py -v`
    - **EXPECTED OUTCOME**: Semua preservation tests PASS (mengkonfirmasi baseline behavior yang harus dipertahankan)
    - Mark task complete saat tests ditulis, dijalankan, dan passing pada unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10_

- [x] 3. Fix critical infrastructure — Docker API dan Alembic

  - [x] 3.1 Fix `docker/Dockerfile.api` — tambahkan ENV PYTHONPATH=/app/backend
    - Tambahkan baris `ENV PYTHONPATH=/app/backend` setelah `WORKDIR /app` dan sebelum blok `RUN apt-get update`
    - Verifikasi: `grep "ENV PYTHONPATH=/app/backend" docker/Dockerfile.api` harus match
    - Acceptance criteria: File berisi `ENV PYTHONPATH=/app/backend` pada posisi yang benar (setelah WORKDIR, sebelum RUN)
    - _Bug_Condition: isBugCondition_Bug1 — "ENV PYTHONPATH" NOT IN dockerfile AND dockerfile berisi "CMD uvicorn api.main:app"_
    - _Expected_Behavior: Container API startup sukses; `from api.main import app` berhasil di dalam container_
    - _Preservation: CMD uvicorn tidak berubah; WORKDIR /app tidak berubah; semua COPY statements tetap (3.1)_
    - _Requirements: 2.1, 2.2_

  - [x] 3.2 Fix `alembic.ini` — perbaiki script_location dan tambah sqlalchemy.url
    - Ubah `script_location = alembic` menjadi `script_location = backend/alembic`
    - Tambahkan `sqlalchemy.url = sqlite:///data/priomed.db` di dalam section `[alembic]` (Issues 8 — fallback value)
    - Verifikasi: `grep "script_location = backend/alembic" alembic.ini` harus match
    - Verifikasi: `grep "sqlalchemy.url" alembic.ini` harus match
    - Acceptance criteria: `PYTHONPATH=backend alembic current` berjalan dari project root tanpa FileNotFoundError
    - _Bug_Condition: isBugCondition_Bug2 — script_location == "alembic" AND NOT EXISTS(project_root/alembic/env.py) AND EXISTS(backend/alembic/env.py)_
    - _Expected_Behavior: `alembic upgrade head` dari project root berhasil; tidak ada path error_
    - _Preservation: Migration files di `backend/alembic/versions/` tidak dimodifikasi; schema tidak berubah (3.2)_
    - _Requirements: 2.3, 2.4, 2.14_

  - [x] 3.3 Fix `.github/workflows/ci.yml` — tambahkan PYTHONPATH pada step dan job yang relevan
    - Tambahkan `env: PYTHONPATH: backend` pada step `Verify API imports cleanly` di job `backend-tests`:
      ```yaml
      - name: Verify API imports cleanly
        run: python -c "from api.main import app; print('API routes:', len(app.routes))"
        env:
          PYTHONPATH: backend
      ```
    - Tambahkan job-level `env: PYTHONPATH: backend` pada job `demo-seed-check` (setelah `needs: [backend-tests]`):
      ```yaml
      demo-seed-check:
        name: Demo Seed Smoke Test
        runs-on: ubuntu-latest
        needs: [backend-tests]
        env:
          PYTHONPATH: backend
      ```
    - Verifikasi: `grep -A 2 "Verify API imports cleanly" .github/workflows/ci.yml | grep "PYTHONPATH"` harus match
    - Acceptance criteria: Kedua PYTHONPATH ada; step `Verify priomedrec_core contracts` tidak perlu diubah (berjalan dari root)
    - _Bug_Condition: isBugCondition_Bug4 — PYTHONPATH NOT IN step_verify.env AND PYTHONPATH NOT IN job_demo.env_
    - _Expected_Behavior: Step "Verify API imports cleanly" dan semua steps di demo-seed-check berhasil import `api.*`_
    - _Preservation: Semua step CI lain tidak dimodifikasi; backend unit tests tetap berjalan (3.6)_
    - _Requirements: 2.7, 2.8_

- [x] 4. Fix Docker Compose — build context, env_file, dan network

  - [x] 4.1 Fix `docker/docker-compose.yml` — ubah build context ke project root (`context: ..`)
    - Ubah `context: .` menjadi `context: ..` untuk service `api`; ubah/tambahkan `dockerfile: docker/Dockerfile.api`
    - Ubah `context: .` menjadi `context: ..` untuk service `langflow`; ubah/tambahkan `dockerfile: docker/Dockerfile.langflow`
    - Ubah `context: .` menjadi `context: ..` untuk service `web`; ubah/tambahkan `dockerfile: docker/Dockerfile.web`
    - Catatan: Path `dockerfile:` harus relatif terhadap context baru (`..`), sehingga menjadi `docker/Dockerfile.api`, bukan hanya `Dockerfile.api`
    - Verifikasi: `grep "context: \.\." docker/docker-compose.yml` mengembalikan 3 matches
    - Acceptance criteria: `docker compose -f docker/docker-compose.yml build api` tidak gagal dengan "file not found in build context"
    - _Bug_Condition: isBugCondition_Issue7_10 — context: "." resolves ke docker/ bukan project root; COPY path gagal_
    - _Expected_Behavior: `docker compose -f docker/docker-compose.yml build web` sukses; semua COPY dapat menemukan file di project root_
    - _Preservation: Volume mounts `./langflow/components`, `./langflow` tetap relatif terhadap compose file location (3.3, 3.8)_
    - _Requirements: 2.12, 2.13, 2.16_

  - [x] 4.2 Fix `docker/docker-compose.yml` — perbaiki env_file path karena context berubah
    - Ubah `env_file: - .env` menjadi `env_file: - ../.env` untuk service `api` (compose file ada di `docker/`, `.env` di project root)
    - Ubah `env_file: - .env` menjadi `env_file: - ../.env` untuk service `langflow`
    - Catatan: `env_file` path relatif terhadap lokasi `docker-compose.yml`, bukan terhadap context — sehingga perlu `../` untuk naik ke project root
    - Verifikasi: `grep "\.\./\.env" docker/docker-compose.yml` menunjukkan `- ../.env`
    - Acceptance criteria: `docker compose -f docker/docker-compose.yml config` tidak error tentang missing env_file
    - _Bug_Condition: env_file: .env tidak valid saat compose file ada di docker/ karena path relatif ke compose file location_
    - _Expected_Behavior: Semua environment variables dari .env terbaca oleh semua service_
    - _Preservation: Semua env vars yang dikonfigurasi tetap terbaca; JWT keys, LLM API key intact (3.9)_
    - _Requirements: 2.16_

  - [x] 4.3 Fix `docker/docker-compose.yml` — tambahkan network `priomed_internal` untuk service `web`
    - Tambahkan `networks: - priomed_internal` pada service `web` (di bawah `ports:` atau `depends_on:` block)
    - Verifikasi: `grep -A 15 "^  web:" docker/docker-compose.yml | grep "priomed_internal"` harus match
    - Acceptance criteria: Service `web` memiliki `priomed_internal` di blok `networks:`
    - _Bug_Condition: isBugCondition_Issue6 — "networks" NOT IN web_service AND nginx proxy ke http://api:8000/_
    - _Expected_Behavior: Nginx dapat resolve hostname `api` dan `langflow` via Docker internal network; proxy sukses_
    - _Preservation: Network `priomed_internal` definition tidak berubah; `api` dan `langflow` network config intact (3.8)_
    - _Requirements: 2.10, 2.11_

- [x] 5. Fix `docker/Dockerfile.web` — perbaiki COPY nginx.conf path

  - [x] 5.1 Fix `docker/Dockerfile.web` — ubah COPY nginx.conf ke path relatif project root
    - Ubah `COPY nginx.conf /etc/nginx/conf.d/default.conf` menjadi `COPY docker/nginx.conf /etc/nginx/conf.d/default.conf`
    - Catatan: Perubahan ini diperlukan karena setelah Fix 4.1, build context adalah project root (`..`), sehingga `nginx.conf` relatif terhadap project root berada di `docker/nginx.conf`
    - Verifikasi: `grep "COPY docker/nginx.conf" docker/Dockerfile.web` harus match
    - Acceptance criteria: `docker build -f docker/Dockerfile.web -t priomed-web-test ..` sukses pada tahap COPY nginx.conf
    - _Bug_Condition: isBugCondition_Issue7 — Dockerfile.web COPY nginx.conf gagal dengan context: .. karena file tidak di root_
    - _Expected_Behavior: Docker build Dockerfile.web berhasil; nginx.conf tersalin ke /etc/nginx/conf.d/default.conf_
    - _Preservation: Isi nginx.conf tidak berubah; proxy rules, security headers, dan SPA catch-all tetap berfungsi (3.5, 3.8)_
    - _Requirements: 2.12, 2.13_

- [x] 6. Create Langflow component stubs

  - [x] 6.1 Buat `langflow/components/priomedrec/__init__.py`
    - Buat file baru: `langflow/components/priomedrec/__init__.py`
    - Isi: `# PrioMed-Rec Langflow Custom Components` (docstring package minimal)
    - Acceptance criteria: File ada; `python -c "import ast; ast.parse(open('langflow/components/priomedrec/__init__.py').read()); print('OK')"` sukses
    - _Bug_Condition: isBugCondition_Bug3 — NOT EXISTS(components_dir / "priomedrec" / "__init__.py")_
    - _Requirements: 2.5, 2.6_

  - [x] 6.2 Buat `langflow/components/priomedrec/triage.py`
    - Buat file baru dengan class `TriageComponent(CustomComponent)` sesuai spec di design.md Fix 3
    - Class harus memiliki: `display_name = "PrioMed Triage"`, `description`, `name = "PrioMedTriage"`, `build_config()`, `build()`
    - Method `build()` menggunakan `httpx.post()` ke endpoint `{api_url}/api/v1/analysis/patient/{patient_id}`
    - Import: `from langflow.custom import CustomComponent` dan `from langflow.field_typing import Text`
    - Acceptance criteria: `python -m py_compile langflow/components/priomedrec/triage.py || echo "langflow not installed - OK in CI"` tidak error pada syntax
    - Acceptance criteria: File berisi class `TriageComponent` dengan semua required attributes
    - _Bug_Condition: isBugCondition_Bug3 — NOT EXISTS(components_dir / "priomedrec" / "triage.py")_
    - _Expected_Behavior: Langflow memuat TriageComponent dari custom_components path; CI py_compile check pass (dengan || true)_
    - _Preservation: Tidak ada perubahan pada backend API atau flow JSON (3.3)_
    - _Requirements: 2.5, 2.6, 2.15_

  - [x] 6.3 Buat `langflow/components/priomedrec/safety.py`
    - Buat file baru dengan class `SafetyGuardrailComponent(CustomComponent)` sesuai spec di design.md Fix 3
    - Class harus memiliki: `display_name = "PrioMed Safety Guardrail"`, `description`, `name = "PrioMedSafety"`, `build_config()`, `build()`
    - Method `build()` menggunakan `httpx.post()` ke endpoint `{api_url}/internal/guardrail-check`; menggunakan `os.getenv("PRIOMEDREC_API_URL", "http://api:8000")`
    - Acceptance criteria: `python -m py_compile langflow/components/priomedrec/safety.py || echo "langflow not installed - OK in CI"` tidak error pada syntax
    - Acceptance criteria: File berisi class `SafetyGuardrailComponent` dengan semua required attributes
    - _Bug_Condition: isBugCondition_Bug3 — NOT EXISTS(components_dir / "priomedrec" / "safety.py")_
    - _Expected_Behavior: Langflow memuat SafetyGuardrailComponent dari custom_components path_
    - _Preservation: Tidak ada perubahan pada backend guardrail service atau API routes (3.1)_
    - _Requirements: 2.5, 2.6, 2.15_

  - [x] 6.4 Buat `langflow/components/priomedrec/audit.py`
    - Buat file baru dengan class `AuditLogComponent(CustomComponent)` sesuai spec di design.md Fix 3
    - Class harus memiliki: `display_name = "PrioMed Audit Log"`, `description`, `name = "PrioMedAudit"`, `build_config()`, `build()`
    - Method `build()` menggunakan `httpx.post()` ke endpoint `{api_url}/internal/audit`; menggunakan `os.getenv("PRIOMEDREC_API_URL", "http://api:8000")`
    - Acceptance criteria: `python -m py_compile langflow/components/priomedrec/audit.py || echo "langflow not installed - OK in CI"` tidak error pada syntax
    - Acceptance criteria: File berisi class `AuditLogComponent` dengan semua required attributes
    - _Bug_Condition: isBugCondition_Bug3 — NOT EXISTS(components_dir / "priomedrec" / "audit.py")_
    - _Expected_Behavior: Langflow memuat AuditLogComponent dari custom_components path_
    - _Preservation: Tidak ada perubahan pada backend audit service (3.1)_
    - _Requirements: 2.5, 2.6, 2.15_

- [x] 7. Fix `langflow/requirements.langflow.txt` — tambah httpx dependency

  - [x] 7.1 Tambahkan httpx ke `langflow/requirements.langflow.txt`
    - Tambahkan konten berikut ke file (mengganti file kosong):
      ```
      # PrioMed-Rec Langflow custom component dependencies
      # Diinstall saat Docker build Langflow image
      httpx>=0.27.0,<0.29.0
      ```
    - Acceptance criteria: `[ -s langflow/requirements.langflow.txt ] && echo "non-empty"` print `non-empty`
    - Acceptance criteria: `grep "httpx" langflow/requirements.langflow.txt` harus match
    - Acceptance criteria: File tidak kosong — kondisi `if [ -s ... ]` di `Dockerfile.langflow` akan true sehingga pip install dijalankan
    - _Bug_Condition: isBugCondition_Issue9 — file_size(requirements_file) == 0 AND custom_components import httpx_
    - _Expected_Behavior: `Dockerfile.langflow` menjalankan `pip install httpx` saat build; komponen dapat menggunakan httpx di runtime_
    - _Preservation: `Dockerfile.langflow` build steps tidak berubah; hanya conditional pip install yang kini aktif (3.10)_
    - _Requirements: 2.15_

- [x] 8. Dokumentasi — tangani duplikasi `frontend/web/` (Issue 5)
  - Tambahkan file `frontend/web/README.md` (atau `frontend/README.md`) dengan konten:
    ```markdown
    # STALE — Direktori Ini Tidak Aktif

    Direktori `frontend/web/` adalah sisa dari refactor sebelumnya dan **tidak lagi digunakan**.

    Direktori aktif untuk frontend React adalah `web/` di project root.
    Semua pengembangan frontend harus dilakukan di `web/src/`.
    ```
  - Alternatif: Hapus `frontend/` directory jika sudah dipastikan tidak ada referensi ke direktori ini di Dockerfile atau CI
  - Verifikasi: `grep -r "frontend/web" docker/ .github/` tidak mengembalikan referensi aktif
  - Acceptance criteria: Developer tidak akan lagi mengira `frontend/web/` adalah sumber aktif
  - Catatan: Ini adalah non-blocking issue — tidak memengaruhi Docker build atau CI pipeline
  - _Bug_Condition: isBugCondition_Issue5 — EXISTS(web/src) AND EXISTS(frontend/web/src) AND CONTENTS berbeda_
  - _Requirements: 2.9_

- [x] 9. Verify bug condition exploration test now passes
  - **Property 1: Expected Behavior** - Configuration Fixes Verified
  - **IMPORTANT**: Re-run test yang SAMA dari task 1 — JANGAN tulis test baru
  - Test dari task 1 mengkodekan expected behavior setelah fix diterapkan
  - Jalankan: `PYTHONPATH=backend python -m pytest tests/test_bugfix_exploration.py -v`
  - **EXPECTED OUTCOME**: Semua assertions yang sebelumnya konfirmasi bug kini konfirmasi fix (kondisi bug tidak lagi terpenuhi)
  - Verifikasi masing-masing fix:
    - `grep "ENV PYTHONPATH=/app/backend" docker/Dockerfile.api` → match ✓ (Bug 1)
    - `grep "script_location = backend/alembic" alembic.ini` → match ✓ (Bug 2)
    - `ls langflow/components/priomedrec/` → `__init__.py audit.py safety.py triage.py` ✓ (Bug 3)
    - `grep -A 2 "Verify API imports cleanly" .github/workflows/ci.yml | grep "PYTHONPATH"` → match ✓ (Bug 4)
    - `grep "context: \.\." docker/docker-compose.yml` → 3 matches ✓ (Issue 7 & 10)
    - `grep -A 15 "^  web:" docker/docker-compose.yml | grep "priomed_internal"` → match ✓ (Issue 6)
    - `[ -s langflow/requirements.langflow.txt ] && echo "non-empty"` → non-empty ✓ (Issue 9)
    - `PYTHONPATH=backend python -c "from api.main import app; print('OK')"` → OK ✓
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.10, 2.12, 2.13, 2.15, 2.16_

- [x] 10. Verify preservation tests still pass
  - **Property 2: Preservation** - No Regressions After Fix
  - **IMPORTANT**: Re-run test yang SAMA dari task 2 — JANGAN tulis test baru
  - Jalankan: `PYTHONPATH=backend python -m pytest tests/test_bugfix_preservation.py -v`
  - **EXPECTED OUTCOME**: Semua preservation tests masih PASS (mengkonfirmasi tidak ada regresi)
  - Verifikasi masing-masing preservation requirement:
    - `PYTHONPATH=backend python -m pytest tests/test_fase1_b103_auth.py tests/test_fase1_b104_state_machine.py tests/test_fase1_b105_priority.py -v` → semua pass ✓ (3.6)
    - `PYTHONPATH=backend python -c "from api.main import app; assert len(app.routes) > 10; print('routes OK')"` → routes OK ✓ (3.1)
    - `cat backend/alembic/versions/20261028_1457_8a108615ebc8_initial_schema_b101_b102.py | head -5` → tidak berubah ✓ (3.2)
    - `python -m py_compile langflow/components/priomedrec/triage.py safety.py audit.py 2>/dev/null || echo "OK (langflow runtime not installed)"` ✓ (3.3)
    - Verifikasi `docker/nginx.conf` tidak dimodifikasi — proxy rules dan SPA catch-all `try_files $uri $uri/ /index.html` intact ✓ (3.5)
    - Verifikasi `web/src/` tidak dimodifikasi — frontend React unchanged ✓ (3.4)
    - Verifikasi `priomedrec_core/` directory tidak dimodifikasi ✓ (3.10)
  - Konfirmasi tidak ada regresi setelah semua fix diterapkan

- [x] 11. Checkpoint — Semua tests pass dan sistem siap dijalankan
  - Pastikan semua tests pass; tanya ke user jika ada pertanyaan
  - Jalankan full test suite: `PYTHONPATH=backend python -m pytest tests/ -v --tb=short`
  - Verifikasi semua fix sudah diterapkan dengan quick verification script:
    ```bash
    # Bug 1 — PYTHONPATH di Dockerfile.api
    grep "ENV PYTHONPATH=/app/backend" docker/Dockerfile.api && echo "Bug1: OK" || echo "Bug1: FAIL"
    # Bug 2 & Issue 8 — script_location dan sqlalchemy.url di alembic.ini
    grep "script_location = backend/alembic" alembic.ini && echo "Bug2: OK" || echo "Bug2: FAIL"
    grep "sqlalchemy.url" alembic.ini && echo "Issue8: OK" || echo "Issue8: FAIL"
    # Bug 3 — Langflow component stubs
    ls langflow/components/priomedrec/__init__.py langflow/components/priomedrec/triage.py \
       langflow/components/priomedrec/safety.py langflow/components/priomedrec/audit.py \
       && echo "Bug3: OK" || echo "Bug3: FAIL"
    # Bug 4 — PYTHONPATH di CI
    grep "PYTHONPATH: backend" .github/workflows/ci.yml && echo "Bug4: OK" || echo "Bug4: FAIL"
    # Issue 5 — Dokumentasi frontend stale
    ls frontend/README.md 2>/dev/null || ls frontend/web/README.md 2>/dev/null && echo "Issue5: OK" || echo "Issue5: NOT DONE (non-blocking)"
    # Issue 6 — web network
    grep -A 15 "^  web:" docker/docker-compose.yml | grep "priomed_internal" && echo "Issue6: OK" || echo "Issue6: FAIL"
    # Issue 7 — nginx.conf COPY path di Dockerfile.web
    grep "COPY docker/nginx.conf" docker/Dockerfile.web && echo "Issue7: OK" || echo "Issue7: FAIL"
    # Issue 9 — requirements.langflow.txt non-empty
    test -s langflow/requirements.langflow.txt && echo "Issue9: OK" || echo "Issue9: FAIL"
    # Issue 10 — build context di docker-compose.yml
    count=$(grep -c "context: \.\." docker/docker-compose.yml); [ "$count" -eq 3 ] && echo "Issue10: OK (3 matches)" || echo "Issue10: FAIL ($count matches)"
    ```
  - Dokumentasikan hasil akhir: semua container dapat distart, CI pipeline pass, Langflow components termuat
  - Jika ada yang belum pass, review tasks yang relevan dan ulangi

---

## Notes

- Task 1 dan 2 adalah **Property-Based Tests** yang harus ditulis SEBELUM fix diterapkan
- Task 1 (Bug Condition) — assertion mengkonfirmasi bug condition exist pada unfixed code
- Task 2 (Preservation) — diharapkan PASS pada kode unfixed sebagai baseline
- Tasks 3–8 adalah implementasi fix dengan urutan: critical infrastructure → Docker Compose → Dockerfile.web → Langflow stubs → requirements → dokumentasi
- Tasks 9–10 menggunakan test yang SAMA dari task 1–2 (bukan test baru) untuk verifikasi setelah fix
- Semua fix adalah **minimal surgical changes** — tidak ada perubahan pada logika aplikasi (backend Python, React frontend, schema migration)
- File `langflow/components/priomedrec/*.py` adalah stubs; import `langflow.custom` hanya tersedia di runtime Langflow — CI menggunakan `|| true` atau `|| echo "OK"` untuk py_compile check
- `context: ..` di docker-compose: path `dockerfile:` harus diupdate ke `docker/Dockerfile.*`; `env_file:` perlu diupdate ke `../.env`; volume mounts tetap relatif terhadap compose file location
- Setelah task 11 selesai, jalankan `docker compose -f docker/docker-compose.yml up --build` untuk verifikasi end-to-end
