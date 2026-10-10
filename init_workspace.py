"""
PrioMed-Rec: Workspace Initializer for IBM Bob Environment
---------------------------------------------------------
Fungsi:
Membuat struktur direktori dan file boilerplate secara otomatis
di dalam workspace IBM Bob.
"""

from pathlib import Path


def init_bob_workspace():
    # 1. Definisi Folder Utama
    folders = [
        "data/raw",
        "data/interim",
        "data/processed",
        "notebooks",
        "models",
        "src",
        "api",
    ]

    # 2. Definisi File Awal dan Isinya
    files = {
        "requirements.txt": (
            "pandas>=2.0.0\n"
            "numpy>=1.24.0\n"
            "scikit-learn>=1.3.0\n"
            "xgboost>=2.0.0\n"
            "shap>=0.42.0\n"
            "fastapi>=0.100.0\n"
            "uvicorn>=0.22.0\n"
            "pydantic>=2.0.0\n"
        ),
        "src/__init__.py": '"""Source package PrioMed-Rec."""\n',
        "src/data_processing.py": '"""Skrip pemrosesan data Synthea."""\n',
        "src/feature_engineering.py": '"""Skrip ekstraksi fitur klinis."""\n',
        "src/discrepancy_rules.py": '"""Rule engine untuk deteksi perbedaan obat."""\n',
        "src/train.py": '"""Skrip pelatihan model ML."""\n',
        "src/predict.py": '"""Skrip fungsi inferensi ML."""\n',
        "api/app.py": '"""Server FastAPI endpoint."""\n',
    }

    base_path = Path.cwd()

    # Buat Folder
    for folder in folders:
        path = base_path / folder
        path.mkdir(parents=True, exist_ok=True)
        print(f"[OK] Folder dibuat: {folder}")

    # Buat File
    for rel_path, content in files.items():
        file_path = base_path / rel_path
        if not file_path.exists():
            file_path.write_text(content, encoding="utf-8")
            print(f"[OK] File dibuat  : {rel_path}")

    print("\nWorkspace PrioMed-Rec di IBM Bob berhasil disiapkan!")


if __name__ == "__main__":
    init_bob_workspace()
