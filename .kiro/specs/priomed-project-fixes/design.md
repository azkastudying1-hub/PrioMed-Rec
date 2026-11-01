# PrioMed-Rec Project Fixes — Bugfix Design

## Overview

Dokumen ini merinci desain teknis untuk memperbaiki 10 bug/issue yang menyebabkan seluruh stack PrioMed-Rec tidak dapat dijalankan maupun di-deploy. Bug-bug tersebut tersebar di enam area: `Dockerfile.api` (PYTHONPATH), `alembic.ini` (script_location), `langflow/components/` (struktur kosong), `.github/workflows/ci.yml` (PYTHONPATH), `docker-compose.yml` (network + build context), dan `langflow/requirements.langflow.txt` (kosong).

Strategi perbaikan adalah **minimal surgical fix** — setiap perubahan hanya menyentuh bagian yang bermasalah tanpa mengubah logika aplikasi yang sudah berjalan. Semua perilaku yang ada (API routes, schema migration, React build, Langflow flow import) harus tetap utuh setelah fix diterapkan.

---

## Glossary

- **Bug_Condition (C)**: Kondisi spesifik yang menyebabkan setiap bug termanifestasi — path yang salah, env var yang hilang, atau file yang tidak ada.
- **Property (P)**: Perilaku yang benar setelah fix — container startup berhasil, import Python sukses, nginx dapat me-proxy request.
- **Preservation**: Semua perilaku yang TIDAK boleh berubah akibat fix — API routes, migration schema, React build, Langflow flows.
- **PYTHONPATH**: Environment variable Python yang menentukan direktori pencarian module.
- **script_location**: Konfigurasi Alembic yang menunjuk ke direktori yang berisi `env.py` dan folder `versions/`.
- **build context**: Direktori root yang digunakan Docker saat menjalankan perintah `COPY` di Dockerfile; semua path di `COPY` relatif terhadap direktori ini.
- **priomed_internal**: Docker bridge network internal yang mengisolasi komunikasi antar-service.
- **Langflow Custom Component**: File Python dengan kelas yang mewarisi `langflow.custom.CustomComponent`, dimuat otomatis oleh Langflow dari `LANGFLOW_COMPONENTS_PATH`.
- **isBugCondition(input)**: Fungsi pseudocode yang mengidentifikasi apakah konfigurasi/state memenuhi kondisi bug.
- **F (original)**: Konfigurasi file sebelum fix.
- **F' (fixed)**: Konfigurasi file setelah fix.

---

## Bug Details

### Bug 1: Dockerfile.api — PYTHONPATH hilang

**Bug Condition:**

```
FUNCTION isBugCondition_Bug1(dockerfile)
  INPUT: dockerfile — konten Dockerfile.api
  OUTPUT: boolean

  RETURN "ENV PYTHONPATH" NOT IN dockerfile
         AND dockerfile CONTAINS "CMD [\"uvicorn\", \"api.main:app\", ...]"
         AND dockerfile CONTAINS "WORKDIR /app"
         AND "COPY . ." COPIES repo root ke /app
         -- Sehingga api/ berada di /app/backend/api/, bukan /app/api/
END FUNCTION
```

**Contoh Manifestasi:**
- `docker-compose up api` → container exit 1 dalam detik dengan `ModuleNotFoundError: No module named 'api'`
- Python mencari `api` di `/app`, `site-packages` — tidak menemukan karena package ada di `/app/backend/api/`
- `docker exec container python -c "import api"` → ImportError

### Bug 2: alembic.ini — script_location salah

**Bug Condition:**

```
FUNCTION isBugCondition_Bug2(alembic_ini)
  INPUT: alembic_ini — konten alembic.ini
  OUTPUT: boolean

  RETURN alembic_ini["script_location"] == "alembic"
         AND NOT EXISTS(project_root / "alembic" / "env.py")
         AND EXISTS(project_root / "backend" / "alembic" / "env.py")
END FUNCTION
```

**Contoh Manifestasi:**
- `alembic upgrade head` dari project root → `FAILED: No such file or directory: '.../alembic/env.py'`
- `alembic revision --autogenerate -m "test"` → FileNotFoundError
- CI step migration check gagal

### Bug 3: langflow/components/ kosong

**Bug Condition:**

```
FUNCTION isBugCondition_Bug3(components_dir)
  INPUT: components_dir — path ke langflow/components/
  OUTPUT: boolean

  RETURN NOT EXISTS(components_dir / "priomedrec" / "triage.py")
         OR NOT EXISTS(components_dir / "priomedrec" / "safety.py")
         OR NOT EXISTS(components_dir / "priomedrec" / "audit.py")
         OR NOT EXISTS(components_dir / "priomedrec" / "__init__.py")
END FUNCTION
```

**Contoh Manifestasi:**
- Langflow container start → UI tidak menampilkan komponen PrioMed-Rec di panel Components
- `docker-compose.yml` mount `./langflow/components:/app/custom_components:ro` → direktori kosong
- CI `py_compile langflow/components/priomedrec/triage.py` → `FileNotFoundError`

### Bug 4: CI GitHub Actions — PYTHONPATH hilang

**Bug Condition:**

```
FUNCTION isBugCondition_Bug4(ci_yml)
  INPUT: ci_yml — konten .github/workflows/ci.yml
  OUTPUT: boolean

  step_verify := ci_yml.jobs["backend-tests"].steps["Verify API imports cleanly"]
  step_seed   := ci_yml.jobs["demo-seed-check"].steps

  RETURN step_verify.env IS NULL OR "PYTHONPATH" NOT IN step_verify.env
         OR ANY step IN step_seed WHERE step imports FROM "api.*"
            AND step.env IS NULL OR "PYTHONPATH" NOT IN step.env
END FUNCTION
```

**Contoh Manifestasi:**
- CI job `backend-tests` — step "Verify API imports cleanly" → `ModuleNotFoundError: No module named 'api'`
- CI job `demo-seed-check` — step "Verify 10 encounters seeded" → `ModuleNotFoundError: No module named 'api'`

### Issue 5: Duplikasi frontend directory

**Bug Condition:**

```
FUNCTION isBugCondition_Issue5(project_root)
  RETURN EXISTS(project_root / "web" / "src")
         AND EXISTS(project_root / "frontend" / "web" / "src")
         AND CONTENTS(project_root / "web") != CONTENTS(project_root / "frontend" / "web")
END FUNCTION
```

### Issue 6: web service tidak join priomed_internal network

**Bug Condition:**

```
FUNCTION isBugCondition_Issue6(docker_compose)
  web_service := docker_compose.services["web"]
  RETURN "networks" NOT IN web_service
         AND docker_compose.services["api"].networks CONTAINS "priomed_internal"
         AND nginx_conf CONTAINS "proxy_pass http://api:8000/"
END FUNCTION
```

**Contoh Manifestasi:**
- `curl http://localhost/api/health` → 502 Bad Gateway dari nginx karena `api` hostname tidak resolve
- Nginx error log: `connect() failed (111: Connection refused) while connecting to upstream`

### Issue 7 & 10: docker-compose.yml — build context salah

**Bug Condition:**

```
FUNCTION isBugCondition_Issue7_10(docker_compose)
  compose_dir   := dirname(docker_compose.file_path)  -- = "docker/"
  build_context := resolve(compose_dir, service.build.context)

  FOR service IN [api, langflow, web]:
    context_path := resolve(compose_dir, service.build.context)
    -- Jika context: "." maka context_path = "docker/" bukan project root
    RETURN context_path == compose_dir
           AND "COPY web/" IN dockerfile  -- COPY akan fail karena web/ tidak ada di docker/
END FUNCTION
```

**Contoh Manifestasi:**
- `docker compose -f docker/docker-compose.yml up --build web` → `COPY failed: file not found in build context: web/package.json`
- `docker compose -f docker/docker-compose.yml up --build api` → `COPY failed: requirements.txt`

**Catatan Analisis:** File-file di `docker/` (`nginx.conf`, `Dockerfile.*`) sudah benar relatif terhadap direktori `docker/`. Yang perlu diubah adalah `context:` di docker-compose dari `.` ke `..` agar Dockerfile bisa `COPY` dari project root.

### Issue 8: alembic.ini — sqlalchemy.url placeholder hilang

**Bug Condition:**

```
FUNCTION isBugCondition_Issue8(alembic_ini)
  RETURN "sqlalchemy.url" NOT IN alembic_ini["alembic"]
         OR alembic_ini["alembic"]["sqlalchemy.url"] == ""
END FUNCTION
```

### Issue 9: requirements.langflow.txt kosong

**Bug Condition:**

```
FUNCTION isBugCondition_Issue9(requirements_file)
  RETURN file_size(requirements_file) == 0
         AND custom_components IMPORT external_packages
END FUNCTION
```

---

## Expected Behavior

### Preservation Requirements

**Perilaku yang TIDAK BOLEH berubah:**
- FastAPI container melayani semua route di port 8000 (3.1)
- Alembic migration `initial_schema` dan `queue_tables` berjalan tanpa perubahan schema (3.2)
- Semua Langflow flow JSON dapat diimport dan dijalankan (3.3)
- Frontend React di `web/` compile tanpa error TypeScript (3.4)
- Nginx SPA catch-all `try_files $uri $uri/ /index.html` tetap berfungsi (3.5)
- Semua backend unit tests pass tanpa modifikasi kode test (3.6)
- `DB_PATH` environment variable tetap mengontrol path database (3.7)
- Service `api` dan `langflow` dapat berkomunikasi via `http://api:8000` (3.8)
- Semua env vars dari `.env` tetap terbaca (3.9)
- `from priomedrec_core.contracts import AnalysisInput, AnalysisResult` tetap berfungsi di Langflow container (3.10)

**Scope Fix:**
Semua perubahan terbatas pada file konfigurasi dan stub file baru. Tidak ada perubahan pada:
- Logika Python di `backend/api/`
- Komponen React di `web/src/`
- Schema Alembic di `backend/alembic/versions/`
- Langflow flow JSON

---

## Hypothesized Root Cause

### Bug 1 — Dockerfile.api
`WORKDIR /app` di-set sebelum `COPY . .` yang menyalin seluruh repo ke `/app`. Hasilnya, `api` package berada di `/app/backend/api/` bukan `/app/api/`. Uvicorn yang dipanggil dengan `api.main:app` mencari module `api` dari Python path default (`/app`, `site-packages`). Karena tidak ada `ENV PYTHONPATH=/app/backend`, import gagal.

### Bug 2 — alembic.ini
`script_location = alembic` mengasumsikan ada folder `alembic/` di direktori kerja saat `alembic` dijalankan (project root). Tapi direktori migration sebenarnya ada di `backend/alembic/`. Tidak ada dokumentasi bahwa perintah Alembic harus dijalankan dari dalam `backend/`.

### Bug 3 — langflow/components/
Direktori `langflow/components/` dibuat sebagai placeholder tapi subdirektori `priomedrec/` dan file component stub tidak pernah dibuat. `Dockerfile.langflow` sudah benar me-copy direktori ini, tapi tidak ada yang di-copy.

### Bug 4 — CI GitHub Actions
Saat menulis CI workflow, `PYTHONPATH: backend` tidak ditambahkan ke step yang melakukan import Python secara langsung (`python -c "from api..."`) — hanya pip install yang dikonfigurasi. Step `Run backend unit tests` mungkin bekerja jika pytest menggunakan `conftest.py` yang memanipulasi `sys.path`, tapi step ad-hoc `python -c` tidak mendapat benefit tersebut.

### Issue 6 — web service network
Service `web` ditambahkan ke `docker-compose.yml` tapi directive `networks:` tidak ditambahkan. Akibatnya `web` bergabung ke network default Docker, bukan `priomed_internal`, sehingga nginx tidak bisa resolve hostname `api`.

### Issue 7 & 10 — build context
`docker-compose.yml` ditempatkan di `docker/` untuk menjaga project root tetap bersih. Tapi `context: .` di setiap service merujuk ke direktori `docker/` itu sendiri, bukan project root. Dockerfile-nya (`Dockerfile.api`, `Dockerfile.web`) mengasumsikan build context adalah project root (`COPY web/`, `COPY . .`). Ketidakcocokan ini menyebabkan semua `COPY` gagal karena path tidak ditemukan di `docker/`.

---

## Correctness Properties

Property 1: Bug Condition — Container dan CI Startup Berhasil

_For any_ konfigurasi di mana bug condition terpenuhi (path salah, PYTHONPATH hilang, file tidak ada), kode setelah fix SHALL menghasilkan startup yang berhasil: container tidak crash, import Python sukses, dan CI pipeline pass.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.10, 2.12, 2.13, 2.15, 2.16**

Property 2: Preservation — Perilaku Existing Tidak Berubah

_For any_ input di mana bug condition TIDAK terpenuhi (request HTTP normal, migration normal, frontend build normal), kode setelah fix SHALL menghasilkan perilaku yang identik dengan kode sebelum fix, mempertahankan semua fungsionalitas yang sudah berjalan.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10**

---

## Fix Implementation

### Fix 1: `docker/Dockerfile.api` — Tambah ENV PYTHONPATH

**File:** `docker/Dockerfile.api`

**Perubahan spesifik:**
Tambahkan `ENV PYTHONPATH=/app/backend` setelah `WORKDIR /app`, sebelum perintah `COPY`.

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Set PYTHONPATH so Python can find packages under /app/backend/
ENV PYTHONPATH=/app/backend

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*
...
```

**Rationale:** `COPY . .` menyalin seluruh repo ke `/app`, sehingga `api` package ada di `/app/backend/api/`. Dengan `PYTHONPATH=/app/backend`, Python dapat menemukan `api.main` tanpa mengubah struktur direktori atau `CMD`.

---

### Fix 2: `alembic.ini` — Perbaiki script_location

**File:** `alembic.ini`

**Perubahan spesifik:**
Ubah `script_location = alembic` menjadi `script_location = backend/alembic`. Tambahkan juga `sqlalchemy.url` placeholder eksplisit (Issue 8).

```ini
[alembic]
script_location = backend/alembic
sqlalchemy.url = sqlite:///data/priomed.db
```

**Rationale:** Direktori migration aktual ada di `backend/alembic/`. `sqlalchemy.url` dibutuhkan sebagai fallback untuk perintah Alembic yang tidak melalui full `env.py` override. Nilai ini akan di-override oleh `env.py` saat migration dijalankan.

---

### Fix 3: Buat `langflow/components/priomedrec/` dengan component stubs

**Files yang dibuat:**
- `langflow/components/priomedrec/__init__.py`
- `langflow/components/priomedrec/triage.py`
- `langflow/components/priomedrec/safety.py`
- `langflow/components/priomedrec/audit.py`

**Struktur Langflow Custom Component:**

Setiap file harus mendefinisikan satu kelas yang mewarisi `CustomComponent` dari Langflow. Struktur minimal yang valid secara syntax dan lulus `py_compile`:

```python
# langflow/components/priomedrec/triage.py
from langflow.custom import CustomComponent
from langflow.field_typing import Text

class TriageComponent(CustomComponent):
    display_name = "PrioMed Triage"
    description  = "Menentukan prioritas triage pasien berdasarkan risk score."
    name         = "PrioMedTriage"

    def build_config(self):
        return {
            "patient_id": {
                "display_name": "Patient ID",
                "type": "str",
                "required": True,
            },
            "api_url": {
                "display_name": "API URL",
                "type": "str",
                "value": "http://api:8000",
            },
        }

    def build(self, patient_id: str, api_url: str = "http://api:8000") -> Text:
        """
        Memanggil endpoint prioritization API dan mengembalikan hasil triage.
        Stub ini harus diimplementasikan penuh sebelum production.
        """
        import httpx
        response = httpx.post(
            f"{api_url}/api/v1/analysis/patient/{patient_id}",
            timeout=25.0,
        )
        response.raise_for_status()
        return str(response.json())
```

```python
# langflow/components/priomedrec/safety.py
from langflow.custom import CustomComponent
from langflow.field_typing import Text

class SafetyGuardrailComponent(CustomComponent):
    display_name = "PrioMed Safety Guardrail"
    description  = "Memvalidasi output AI terhadap safety constraints klinis."
    name         = "PrioMedSafety"

    def build_config(self):
        return {
            "analysis_result": {
                "display_name": "Analysis Result (JSON)",
                "type": "str",
                "required": True,
            },
        }

    def build(self, analysis_result: str) -> Text:
        """
        Menjalankan guardrail checks pada hasil analisis.
        Stub ini harus diimplementasikan penuh sebelum production.
        """
        import json, httpx, os
        api_url = os.getenv("PRIOMEDREC_API_URL", "http://api:8000")
        payload = json.loads(analysis_result)
        response = httpx.post(
            f"{api_url}/internal/guardrail-check",
            json=payload,
            timeout=15.0,
        )
        response.raise_for_status()
        return str(response.json())
```

```python
# langflow/components/priomedrec/audit.py
from langflow.custom import CustomComponent
from langflow.field_typing import Text

class AuditLogComponent(CustomComponent):
    display_name = "PrioMed Audit Log"
    description  = "Mencatat audit trail untuk semua keputusan AI ke backend."
    name         = "PrioMedAudit"

    def build_config(self):
        return {
            "event_type": {
                "display_name": "Event Type",
                "type": "str",
                "required": True,
            },
            "payload": {
                "display_name": "Payload (JSON)",
                "type": "str",
                "required": True,
            },
        }

    def build(self, event_type: str, payload: str) -> Text:
        """
        Mengirim audit event ke backend PrioMed-Rec.
        Stub ini harus diimplementasikan penuh sebelum production.
        """
        import json, httpx, os
        api_url = os.getenv("PRIOMEDREC_API_URL", "http://api:8000")
        data    = {"event_type": event_type, "payload": json.loads(payload)}
        response = httpx.post(
            f"{api_url}/internal/audit",
            json=data,
            timeout=10.0,
        )
        response.raise_for_status()
        return f"Audit logged: {event_type}"
```

**Catatan Import:** Langflow custom components menggunakan `langflow.custom.CustomComponent` dan `langflow.field_typing`. Import ini hanya tersedia di runtime Langflow, sehingga `py_compile` di CI menggunakan `|| true` (sudah ada di ci.yml) — ini adalah desain yang benar.

---

### Fix 4: `.github/workflows/ci.yml` — Tambah PYTHONPATH

**File:** `.github/workflows/ci.yml`

**Perubahan spesifik:**

1. Tambahkan `env: PYTHONPATH: backend` pada step `Verify API imports cleanly` di job `backend-tests`:

```yaml
- name: Verify API imports cleanly
  run: python -c "from api.main import app; print('API routes:', len(app.routes))"
  env:
    PYTHONPATH: backend
```

2. Tambahkan `env: PYTHONPATH: backend` pada job-level `demo-seed-check` (agar semua steps yang import `api.*` mendapat PYTHONPATH yang benar):

```yaml
demo-seed-check:
  name: Demo Seed Smoke Test
  runs-on: ubuntu-latest
  needs: [backend-tests]
  env:
    PYTHONPATH: backend
```

**Rationale:** Job-level `env` lebih maintainable karena semua steps di job tersebut otomatis mendapat variable yang sama, tanpa perlu menambahkan `env:` ke setiap step secara individual.

---

### Fix 5: `docker/docker-compose.yml` — Perbaiki build context dan tambah network untuk web

**File:** `docker/docker-compose.yml`

**Perubahan spesifik:**

**5a. Ubah `context: .` menjadi `context: ..` untuk semua service:**

```yaml
services:
  api:
    build:
      context: ..          # project root (docker/../)
      dockerfile: docker/Dockerfile.api
  langflow:
    build:
      context: ..          # project root
      dockerfile: docker/Dockerfile.langflow
  web:
    build:
      context: ..          # project root
      dockerfile: docker/Dockerfile.web
      args:
        VITE_DATA_MODE: live
```

**Catatan:** Saat context berubah ke `..`, path `dockerfile:` harus relatif terhadap context baru (`..`), sehingga menjadi `docker/Dockerfile.api` bukan hanya `Dockerfile.api`.

**5b. Tambahkan `networks:` pada service `web`:**

```yaml
  web:
    build:
      context: ..
      dockerfile: docker/Dockerfile.web
      args:
        VITE_DATA_MODE: live
    ports:
      - "80:80"
    networks:
      - priomed_internal    # ← tambahkan ini
    depends_on:
      api:
        condition: service_healthy
      langflow:
        condition: service_healthy
    restart: unless-stopped
```

**5c. Perbaiki `env_file` path** karena dengan `context: ..` path relatif untuk `env_file` tetap relatif terhadap lokasi `docker-compose.yml` itu sendiri (bukan context). Karena `docker-compose.yml` ada di `docker/` dan `.env` ada di project root: 

```yaml
  api:
    env_file:
      - ../.env
  langflow:
    env_file:
      - ../.env
```

**Rationale untuk strategi `context: ..` vs memindahkan compose ke root:**
- Memindahkan `docker-compose.yml` ke root akan mengubah semua path relatif yang sudah ada (volume mounts `./langflow/...`, `./langflow/components/...`) dan merusak workflow developer yang sudah terbiasa dengan `docker compose -f docker/docker-compose.yml`.
- Mengubah ke `context: ..` hanya mengubah dua hal: prefix `context:` dan `dockerfile:` path. Volume mounts di `docker-compose.yml` tetap relatif terhadap lokasi compose file, sehingga `./langflow/components` masih benar.

---

### Fix 6: `docker/nginx.conf` — Verifikasi dan perbaiki (Issue 7)

**File:** `docker/nginx.conf` (sudah ada, verifikasi bahwa konfigurasi sudah benar)

Berdasarkan analisis file, `nginx.conf` yang ada di `docker/nginx.conf` sudah benar. Namun dengan fix build context (`context: ..`), `Dockerfile.web` yang berisi `COPY nginx.conf /etc/nginx/conf.d/default.conf` akan mencari `nginx.conf` di project root, bukan di `docker/`. Perlu diubah path di `Dockerfile.web`:

**File:** `docker/Dockerfile.web`

```dockerfile
# Sebelumnya (dengan context: .)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Setelah fix (dengan context: ..)
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
```

**Verifikasi nginx.conf sudah mencakup:**
- ✅ Proxy `/api/` → `http://api:8000/`
- ✅ Proxy `/langflow/` → `http://langflow:7860/`
- ✅ SPA catch-all: `try_files $uri $uri/ /index.html`
- ✅ Security headers (X-Frame-Options, X-Content-Type-Options)
- ✅ Gzip compression
- ✅ `proxy_read_timeout` yang cukup untuk AI calls (120s untuk api, 180s untuk langflow)

---

### Fix 7: `langflow/requirements.langflow.txt` — Tambah dependencies

**File:** `langflow/requirements.langflow.txt`

```
# PrioMed-Rec Langflow custom component dependencies
# Diinstall saat Docker build Langflow image
httpx>=0.27.0,<0.29.0
```

**Rationale:** Component stubs menggunakan `httpx` untuk memanggil API. `Dockerfile.langflow` sudah punya conditional install: `if [ -s /tmp/requirements.langflow.txt ]`. Dengan menambahkan `httpx`, kondisi ini akan terpenuhi dan dependency akan diinstall.

---

### Fix 8: `docker/Dockerfile.api` — Perbaiki COPY path setelah context change

**File:** `docker/Dockerfile.api`

Dengan `context: ..` (project root), `COPY . .` sudah benar (menyalin project root ke `/app`). `COPY requirements.txt .` juga benar karena `requirements.txt` ada di project root. Tidak ada perubahan tambahan selain ENV PYTHONPATH dari Fix 1.

---

### Fix 9: `docker/Dockerfile.langflow` — Perbaiki COPY path setelah context change

**File:** `docker/Dockerfile.langflow`

```dockerfile
# Sebelumnya (dengan context: .)
COPY priomedrec_core /app/priomedrec_core
COPY langflow/components /app/custom_components
COPY langflow/requirements.langflow.txt /tmp/requirements.langflow.txt

# Tidak perlu diubah — dengan context: .., path ini sudah relatif terhadap project root
# dan priomedrec_core/, langflow/ ada di project root. ✅ Sudah benar.
```

**Catatan:** `Dockerfile.langflow` tidak perlu diubah selain konsekuensi dari perubahan context (yang justru membuatnya lebih benar dari sebelumnya — sebelumnya `context: .` = `docker/` maka `COPY priomedrec_core` akan gagal karena `priomedrec_core/` tidak ada di `docker/`).

---

### Issue 5: Dokumentasi — `frontend/web/` stale

**Rekomendasi:** Tambahkan note di `frontend/web/README.md` (atau hapus direktori) bahwa direktori ini stale dan `web/` adalah sumber aktif. Ini adalah non-blocking issue dan tidak memerlukan perubahan konfigurasi Docker.

---

## Testing Strategy

### Validation Approach

Testing mengikuti dua fase: (1) jalankan exploratory tests pada konfigurasi SEBELUM fix untuk membuktikan bug, kemudian (2) jalankan fix-checking dan preservation tests pada konfigurasi SETELAH fix.

---

### Exploratory Bug Condition Checking

**Goal:** Konfirmasi root cause sebelum fix diterapkan.

**Test Plan:** Simulasi kondisi bug dengan menjalankan perintah yang secara eksplisit memicu kondisi error.

**Test Cases:**

1. **Bug 1 — Container startup** (akan gagal pada kode unfixed):
   ```bash
   docker build -f docker/Dockerfile.api -t priomed-api-test .
   docker run --rm priomed-api-test python -c "from api.main import app"
   # Expected: ModuleNotFoundError: No module named 'api'
   ```

2. **Bug 2 — Alembic command** (akan gagal pada kode unfixed):
   ```bash
   alembic current
   # Expected: FileNotFoundError: .../alembic/env.py not found
   ```

3. **Bug 3 — Component file existence** (akan gagal pada kode unfixed):
   ```bash
   python -m py_compile langflow/components/priomedrec/triage.py
   # Expected: FileNotFoundError
   ```

4. **Bug 4 — CI import tanpa PYTHONPATH** (akan gagal pada kode unfixed):
   ```bash
   python -c "from api.main import app"
   # Expected: ModuleNotFoundError (tanpa PYTHONPATH=backend)
   PYTHONPATH=backend python -c "from api.main import app"
   # Expected: sukses
   ```

5. **Issue 6 — nginx proxy resolution** (akan gagal pada kode unfixed):
   ```bash
   docker compose -f docker/docker-compose.yml up -d
   curl http://localhost/api/health
   # Expected: 502 Bad Gateway
   ```

6. **Issue 10 — build context** (akan gagal pada kode unfixed):
   ```bash
   docker compose -f docker/docker-compose.yml build web
   # Expected: COPY failed: file not found in build context: web/package.json
   ```

**Expected Counterexamples:**
- Import error karena PYTHONPATH tidak diset
- Path error karena build context salah
- File not found karena komponen stub tidak ada

---

### Fix Checking

**Goal:** Verifikasi bahwa setelah fix diterapkan, semua bug condition tidak lagi terpenuhi.

**Pseudocode:**
```
FOR ALL config_file IN [Dockerfile.api, alembic.ini, ci.yml, docker-compose.yml, requirements.langflow.txt]:
  result := verify_fix(config_file)
  ASSERT NOT isBugCondition(config_file)

FOR ALL component IN [triage.py, safety.py, audit.py]:
  ASSERT EXISTS(langflow/components/priomedrec/component)
  ASSERT py_compile_succeeds(component)
END FOR
```

**Test Cases:**

1. **Bug 1 Fix Check:**
   ```bash
   grep "ENV PYTHONPATH=/app/backend" docker/Dockerfile.api
   # Expected: match ditemukan
   docker build -f docker/Dockerfile.api -t priomed-api-fixed --build-context project=. .
   docker run --rm priomed-api-fixed python -c "from api.main import app; print('OK')"
   # Expected: "OK"
   ```

2. **Bug 2 Fix Check:**
   ```bash
   grep "script_location = backend/alembic" alembic.ini
   # Expected: match ditemukan
   PYTHONPATH=backend alembic current
   # Expected: berhasil (mungkin "No current revision" tapi tidak error)
   ```

3. **Bug 3 Fix Check:**
   ```bash
   ls langflow/components/priomedrec/
   # Expected: __init__.py  audit.py  safety.py  triage.py
   python -m py_compile langflow/components/priomedrec/triage.py && echo OK
   python -m py_compile langflow/components/priomedrec/safety.py && echo OK
   python -m py_compile langflow/components/priomedrec/audit.py && echo OK
   ```

4. **Bug 4 Fix Check:**
   ```bash
   grep -A 2 "Verify API imports cleanly" .github/workflows/ci.yml | grep "PYTHONPATH"
   # Expected: match ditemukan
   ```

5. **Issue 6 Fix Check:**
   ```bash
   grep -A 5 "^  web:" docker/docker-compose.yml | grep "priomed_internal"
   # Expected: match ditemukan
   ```

6. **Issue 10 Fix Check:**
   ```bash
   grep "context: \.\." docker/docker-compose.yml
   # Expected: 3 matches (api, langflow, web)
   docker compose -f docker/docker-compose.yml build web
   # Expected: build sukses
   ```

---

### Preservation Checking

**Goal:** Verifikasi bahwa fix tidak mengubah perilaku yang sudah benar.

**Pseudocode:**
```
FOR ALL behavior IN preserved_behaviors:
  ASSERT behavior_after_fix(input) == behavior_before_fix(input)
END FOR
```

**Test Cases:**

1. **Preservation 3.1 — API routes tetap berfungsi:**
   ```bash
   PYTHONPATH=backend python -c "from api.main import app; assert len(app.routes) > 10; print(f'{len(app.routes)} routes OK')"
   ```

2. **Preservation 3.2 — Migration schema tidak berubah:**
   ```bash
   PYTHONPATH=backend alembic upgrade head
   PYTHONPATH=backend alembic current
   # Expected: head tanpa error, tidak ada perubahan schema
   ```

3. **Preservation 3.4 — Frontend build tetap berjalan:**
   ```bash
   cd web && npm ci && npm run build
   # Expected: build sukses tanpa TypeScript error
   ```

4. **Preservation 3.6 — Backend tests tetap pass:**
   ```bash
   PYTHONPATH=backend python -m pytest tests/test_fase1_b103_auth.py tests/test_fase1_b104_state_machine.py -v
   # Expected: semua pass
   ```

5. **Preservation 3.10 — priomedrec_core import di Langflow:**
   ```bash
   docker compose -f docker/docker-compose.yml run --rm langflow \
     python -c "from priomedrec_core.contracts import AnalysisInput, AnalysisResult; print('OK')"
   # Expected: "OK"
   ```

**Testing Approach:** Property-based testing direkomendasikan untuk preservation checking karena:
- Menghasilkan banyak test case input secara otomatis
- Menangkap edge cases yang mungkin tidak terpikirkan
- Memberikan jaminan kuat bahwa perilaku tidak berubah

**Property-Based Test Plan:**
- Generate berbagai HTTP request ke API endpoints dan verifikasi response shape tidak berubah
- Generate berbagai kombinasi environment variables dan verifikasi startup behavior

---

### Unit Tests

- Test bahwa `ENV PYTHONPATH` ada di `Dockerfile.api` (grep/parse test)
- Test bahwa `script_location` menunjuk ke path yang valid dan direktori tersebut berisi `env.py`
- Test bahwa semua 3 component files ada dan valid secara Python syntax
- Test bahwa `PYTHONPATH: backend` ada di semua steps yang membutuhkan import `api.*` di CI
- Test bahwa service `web` memiliki network `priomed_internal`
- Test bahwa semua `context:` di docker-compose menunjuk ke `..`

### Property-Based Tests

- Generate berbagai request payload ke FastAPI dan verifikasi semua route masih merespons (preservation 3.1)
- Generate berbagai patient ID dan verifikasi prioritization endpoint masih berfungsi (preservation 3.1)
- Generate berbagai kombinasi environment config dan verifikasi startup tidak crash (3.7, 3.9)

### Integration Tests

- Full `docker compose build` berhasil tanpa error untuk semua services
- `docker compose up` berhasil dengan semua service healthy
- `curl http://localhost/api/health` mengembalikan 200 OK melalui nginx proxy
- `curl http://localhost/` mengembalikan `index.html` (SPA catch-all)
- Alembic `upgrade head` berhasil dari project root
- CI pipeline pass tanpa modifikasi test code
