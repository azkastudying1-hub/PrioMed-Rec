# Bugfix Requirements Document

## Introduction

Dokumen ini merangkum seluruh bug dan isu yang ditemukan pada proyek PrioMed-Rec — sebuah aplikasi medis dengan stack FastAPI (backend), React/Vite (frontend di `web/`), Langflow (AI orchestration), dan Docker. Bug-bug ini menyebabkan container crash saat startup, CI pipeline gagal, serta custom Langflow components tidak termuat, sehingga sistem tidak dapat dijalankan maupun di-deploy secara benar.

Terdapat 4 critical bugs, 4 significant issues, dan 2 minor issues yang perlu diperbaiki secara sistematis agar seluruh stack dapat berjalan dengan benar.

---

## Bug Analysis

### Current Behavior (Defect)

#### Bug 1: Dockerfile.api — ModuleNotFoundError saat startup

1.1 WHEN container API dijalankan dengan `CMD ["uvicorn", "api.main:app", ...]` dan `WORKDIR /app` tanpa `ENV PYTHONPATH=/app/backend` THEN container crash dengan `ModuleNotFoundError: No module named 'api'` karena Python path tidak menyertakan `/app/backend`

1.2 WHEN Docker build menyalin seluruh repo ke `/app` sehingga package `api` ada di `/app/backend/api/` THEN uvicorn tidak dapat menemukan module `api.main` karena root Python path hanya `/app`

#### Bug 2: alembic.ini — script_location salah

1.3 WHEN `alembic upgrade head` dijalankan dari project root dengan `script_location = alembic` di `alembic.ini` THEN perintah gagal karena direktori `alembic/` tidak ada di root project (yang sebenarnya ada di `backend/alembic/`)

1.4 WHEN developer mencoba generate migration baru dengan `alembic revision --autogenerate` dari root THEN Alembic melaporkan error path tidak ditemukan

#### Bug 3: langflow/components/ kosong — custom components tidak ada

1.5 WHEN `docker-compose.yml` me-mount `./langflow/components:/app/custom_components:ro` dan Langflow container di-start THEN Langflow berjalan tanpa custom components PrioMed-Rec karena direktori `langflow/components/` kosong dan subdirektori `priomedrec/` tidak ada

1.6 WHEN CI workflow menjalankan `python -m py_compile langflow/components/priomedrec/triage.py` THEN step gagal karena file `triage.py`, `safety.py`, dan `audit.py` tidak ada di `langflow/components/priomedrec/`

#### Bug 4: CI GitHub Actions — PYTHONPATH tidak diset

1.7 WHEN step `Verify API imports cleanly` menjalankan `python -c "from api.main import app"` di CI tanpa `PYTHONPATH: backend` THEN step gagal dengan `ModuleNotFoundError: No module named 'api'`

1.8 WHEN step `demo-seed-check` menjalankan `from api.db.session import session_scope` tanpa `PYTHONPATH: backend` THEN import gagal dan seed test tidak dapat dijalankan

#### Issue 5: Duplikasi frontend directory

1.9 WHEN developer memodifikasi file di `web/src/` THEN perubahan tidak tercermin di `frontend/web/src/` karena keduanya adalah direktori terpisah dengan konten berbeda, menyebabkan kebingungan tentang direktori mana yang aktif

1.10 WHEN Docker build `Dockerfile.web` berjalan dengan `COPY web/ .` THEN build menggunakan `web/` bukan `frontend/web/`, namun `frontend/web/` yang stale tetap ada dan menyebabkan kebingungan

#### Issue 6: docker-compose.yml — web service tidak join priomed_internal network

1.11 WHEN service `web` di `docker-compose.yml` tidak memiliki `networks:` directive THEN nginx di dalam container web tidak dapat me-forward request ke `api:8000` via internal network karena `web` tidak tergabung di network `priomed_internal`

1.12 WHEN nginx di container web mencoba proxy request ke `http://api:8000/` THEN request gagal karena hostname `api` tidak dapat di-resolve dari network default Docker

#### Issue 7: nginx.conf tidak ada di root Docker context

1.13 WHEN `Dockerfile.web` menjalankan `COPY nginx.conf /etc/nginx/conf.d/default.conf` dengan build context `.` dari dalam direktori `docker/` THEN Docker build **tidak gagal** karena `nginx.conf` ada di `docker/nginx.conf` yang merupakan context path yang benar — **namun ini bergantung pada asumsi bahwa docker-compose dijalankan dari dalam direktori `docker/`**

1.14 WHEN `docker-compose.yml` di dalam direktori `docker/` menggunakan `context: .` THEN build context merujuk ke direktori `docker/` bukan project root, sehingga `COPY web/` di `Dockerfile.web` akan gagal karena `web/` tidak ada di dalam `docker/`

#### Issue 8: alembic.ini tidak punya sqlalchemy.url

1.15 WHEN perintah Alembic dijalankan dalam mode yang tidak melalui `env.py` secara penuh (misalnya `alembic current`, `alembic history`) THEN Alembic mungkin memerlukan `sqlalchemy.url` yang valid di `alembic.ini` sebagai fallback karena tidak semua perintah mengeksekusi override di `env.py`

#### Issue 9: langflow/requirements.langflow.txt kosong

1.16 WHEN `Dockerfile.langflow` menjalankan `if [ -s /tmp/requirements.langflow.txt ]` THEN kondisi false karena file kosong, sehingga tidak ada dependencies tambahan yang diinstall untuk custom components

#### Issue 10: docker-compose.yml — build context path tidak konsisten

1.17 WHEN `docker-compose.yml` berada di subdirektori `docker/` dan menggunakan `context: .` THEN build context adalah `docker/` bukan project root, sehingga semua `COPY` di Dockerfile yang mengasumsikan struktur project root (`COPY web/`, `COPY . .`, `COPY priomedrec_core`, dll.) akan gagal karena path tidak ditemukan

---

### Expected Behavior (Correct)

#### Bug 1: Dockerfile.api — PYTHONPATH harus diset

2.1 WHEN container API dijalankan THEN `ENV PYTHONPATH=/app/backend` harus diset di `Dockerfile.api` sehingga Python dapat menemukan package `api` di `/app/backend/api/`

2.2 WHEN uvicorn menjalankan `api.main:app` THEN module `api.main` SHALL dapat di-import tanpa error karena `/app/backend` ada di Python path

#### Bug 2: alembic.ini — script_location harus benar

2.3 WHEN `alembic upgrade head` dijalankan dari project root THEN `script_location` di `alembic.ini` SHALL menunjuk ke `backend/alembic` sehingga Alembic menemukan direktori migration yang benar

2.4 WHEN developer menjalankan perintah Alembic apapun dari project root THEN Alembic SHALL menemukan script environment dan migration versions tanpa error path

#### Bug 3: langflow/components — struktur direktori dan file komponen harus ada

2.5 WHEN Langflow container di-start THEN direktori `langflow/components/priomedrec/` SHALL ada dan berisi file komponen (`triage.py`, `safety.py`, `audit.py`) sehingga custom components PrioMed-Rec termuat

2.6 WHEN CI menjalankan syntax check pada komponen Langflow THEN file `langflow/components/priomedrec/triage.py`, `safety.py`, dan `audit.py` SHALL ada dan valid secara syntax Python

#### Bug 4: CI GitHub Actions — PYTHONPATH harus diset

2.7 WHEN step `Verify API imports cleanly` dijalankan di CI THEN environment variable `PYTHONPATH: backend` SHALL ada pada step tersebut sehingga `from api.main import app` berhasil

2.8 WHEN job `demo-seed-check` menjalankan import `from api.db.session import session_scope` THEN `PYTHONPATH: backend` SHALL diset pada seluruh steps di job tersebut

#### Issue 5: Duplikasi frontend — satu sumber kebenaran

2.9 WHEN developer bekerja dengan kode frontend THEN hanya satu direktori frontend (`web/`) yang SHALL dipertahankan sebagai sumber aktif; direktori `frontend/web/` SHALL dihapus atau diarsipkan untuk menghilangkan ambiguitas

#### Issue 6: web service harus join priomed_internal network

2.10 WHEN service `web` di `docker-compose.yml` dikonfigurasi THEN service tersebut SHALL memiliki `networks: - priomed_internal` sehingga nginx dapat me-resolve hostname `api` dan `langflow` via internal Docker network

2.11 WHEN nginx di container web mem-proxy request ke `http://api:8000/` THEN request SHALL berhasil diteruskan ke service `api` karena keduanya berada di network yang sama

#### Issue 7: Build context harus konsisten

2.12 WHEN Docker Compose menjalankan build THEN build context SHALL merujuk ke project root (bukan subdirektori `docker/`) sehingga semua `COPY` di Dockerfile dapat menemukan file yang dibutuhkan

2.13 WHEN `Dockerfile.web` menjalankan `COPY nginx.conf ...` THEN file `nginx.conf` SHALL tersedia di build context path yang digunakan

#### Issue 8: alembic.ini harus memiliki sqlalchemy.url fallback

2.14 WHEN perintah Alembic dijalankan THEN `alembic.ini` SHALL memiliki `sqlalchemy.url` yang valid atau placeholder eksplisit di section `[alembic]` sehingga tidak ada perintah Alembic yang gagal karena missing key

#### Issue 9: requirements.langflow.txt harus berisi dependencies

2.15 WHEN `Dockerfile.langflow` menjalankan pip install dari `requirements.langflow.txt` THEN file tersebut SHALL berisi setidaknya daftar dependencies dasar yang dibutuhkan custom components PrioMed-Rec

#### Issue 10: docker-compose.yml context path harus ke project root

2.16 WHEN `docker-compose.yml` di direktori `docker/` mendefinisikan build context THEN setiap service SHALL menggunakan `context: ..` (parent directory) sebagai build context agar semua Dockerfile dapat mengakses file di project root

---

### Unchanged Behavior (Regression Prevention)

3.1 WHEN API container berjalan dengan benar THEN service FastAPI SHALL CONTINUE TO melayani request di port 8000 dengan semua route yang telah dikonfigurasi

3.2 WHEN database migration dijalankan dengan Alembic THEN migration schema yang sudah ada (`initial_schema`, `queue_tables`) SHALL CONTINUE TO berjalan tanpa perubahan pada data atau struktur tabel

3.3 WHEN Langflow container berjalan THEN semua flow JSON yang ada (`Master Pipeline.json`, `HITL Review Gate & Audit Trail.json`, `Tool-Use Copilot.json`) SHALL CONTINUE TO dapat diimport dan dijalankan

3.4 WHEN frontend di `web/` di-build THEN semua komponen React yang sudah ada SHALL CONTINUE TO ter-compile tanpa error TypeScript

3.5 WHEN nginx di container web menerima request SPA THEN catch-all route ke `index.html` SHALL CONTINUE TO berfungsi untuk client-side routing React

3.6 WHEN CI menjalankan backend unit tests THEN semua test di `tests/test_fase1_*`, `tests/test_fase3_*`, dan test lainnya SHALL CONTINUE TO pass tanpa modifikasi kode test

3.7 WHEN environment variable `DB_PATH` diset THEN database session SHALL CONTINUE TO menggunakan path yang dikonfigurasi tanpa perubahan perilaku

3.8 WHEN service `api` dan `langflow` berkomunikasi via internal network THEN endpoint `http://api:8000` yang dipanggil oleh Langflow components SHALL CONTINUE TO dapat diakses

3.9 WHEN container dijalankan dengan `env_file: .env` THEN semua environment variables yang sudah terkonfigurasi (JWT keys, LLM API key, service keys) SHALL CONTINUE TO terbaca dengan benar

3.10 WHEN `Dockerfile.langflow` me-copy `priomedrec_core` ke `/app/priomedrec_core` THEN import `from priomedrec_core.contracts import AnalysisInput, AnalysisResult` SHALL CONTINUE TO berfungsi di dalam Langflow container
