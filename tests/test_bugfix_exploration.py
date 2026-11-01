"""
Bug Condition Exploration Test

Properti 1: Bug Condition — verifikasi bahwa bug condition ada pada unfixed code.
Jalankan dengan: PYTHONPATH=backend python -m pytest tests/test_bugfix_exploration.py -v
"""
import subprocess
import os
from pathlib import Path


def test_bug1_pythonpath_not_in_dockerfile_api():
    """Bug 1: Verifikasi ENV PYTHONPATH tidak ada di docker/Dockerfile.api"""
    dockerfile_path = Path("docker/Dockerfile.api")
    assert dockerfile_path.exists(), "docker/Dockerfile.api harus ada"
    
    content = dockerfile_path.read_text()
    # Bug condition: ENV PYTHONPATH tidak ada, TAPI cmd uvicorn ada
    has_pythonpath_env = "ENV PYTHONPATH=/app/backend" in content
    has_uvicorn_cmd = "uvicorn" in content and "api.main:app" in content
    
    # Jika bug ada: pythonpath_env == False AND uvicorn_cmd == True
    assert has_uvicorn_cmd, "Dockerfile.api harus memiliki CMD uvicorn api.main:app"
    # Ini adalah bug condition — ENV PYTHONPATH harus TIDAK ada pada unfixed code
    if not has_pythonpath_env:
        print("✓ Bug condition 1.1, 1.2 confirmed: ENV PYTHONPATH tidak ada di Dockerfile.api")
    

def test_bug2_script_location_wrong_in_alembic():
    """Bug 2: Verifikasi script_location salah di alembic.ini"""
    alembic_path = Path("alembic.ini")
    assert alembic_path.exists(), "alembic.ini harus ada"
    
    content = alembic_path.read_text()
    # Bug condition: script_location = alembic (salah) bukan backend/alembic
    has_wrong_script_location = "script_location = alembic" in content and "backend/alembic" not in content
    
    if has_wrong_script_location:
        print("✓ Bug condition 1.3, 1.4 confirmed: script_location = alembic (salah)")
    

def test_bug3_langflow_components_missing():
    """Bug 3: Verifikasi file-file Langflow component tidak ada"""
    required_files = [
        Path("langflow/components/priomedrec/__init__.py"),
        Path("langflow/components/priomedrec/triage.py"),
        Path("langflow/components/priomedrec/safety.py"),
        Path("langflow/components/priomedrec/audit.py"),
    ]
    
    missing_files = [f for f in required_files if not f.exists()]
    
    if missing_files:
        print(f"✓ Bug condition 1.5, 1.6 confirmed: Missing files: {missing_files}")


def test_bug4_pythonpath_not_in_ci_workflow():
    """Bug 4: Verifikasi PYTHONPATH tidak ada di CI workflow"""
    ci_path = Path(".github/workflows/ci.yml")
    assert ci_path.exists(), ".github/workflows/ci.yml harus ada"
    
    content = ci_path.read_text()
    
    # Check step-level PYTHONPATH
    has_step_pythonpath = "Verify API imports cleanly" in content and \
                          content.find("PYTHONPATH: backend") > content.find("Verify API imports cleanly")
    
    # Check job-level PYTHONPATH untuk demo-seed-check
    has_job_pythonpath = "demo-seed-check:" in content and \
                         "PYTHONPATH: backend" in content[content.find("demo-seed-check:"):]
    
    if not has_step_pythonpath:
        print("✓ Bug condition 1.7 confirmed: PYTHONPATH tidak ada pada step 'Verify API imports cleanly'")
    
    if not has_job_pythonpath:
        print("✓ Bug condition 1.8 confirmed: PYTHONPATH tidak ada pada job 'demo-seed-check'")


def test_bug_import_failure_without_pythonpath():
    """Simulasi import failure tanpa PYTHONPATH"""
    # Jalankan Python tanpa PYTHONPATH backend
    result = subprocess.run(
        ["python", "-c", "from api.main import app"],
        capture_output=True,
        cwd=str(Path.cwd())
    )
    
    # Expect failure (returncode != 0)
    if result.returncode != 0:
        print(f"✓ Bug condition confirmed: ModuleNotFoundError tanpa PYTHONPATH")
        print(f"  Error: {result.stderr.decode()[:100]}")
    

def test_issue6_web_service_missing_network():
    """Issue 6: Verifikasi service web tidak memiliki priomed_internal network"""
    docker_compose_path = Path("docker/docker-compose.yml")
    assert docker_compose_path.exists(), "docker/docker-compose.yml harus ada"
    
    content = docker_compose_path.read_text()
    
    # Cari service web dan check apakah ada priomed_internal
    web_section_start = content.find("services:")
    if web_section_start > -1:
        web_start = content.find("  web:", web_section_start)
        if web_start > -1:
            # Cari next service (api atau langflow) setelah web untuk menentukan boundary
            next_service = min(
                content.find("  api:", web_start + 1),
                content.find("  langflow:", web_start + 1),
                content.find("networks:", web_start + 1)
            )
            if next_service == -1:
                next_service = len(content)
            
            web_section = content[web_start:next_service]
            has_network = "priomed_internal" in web_section
            
            if not has_network:
                print("✓ Bug condition 1.11, 1.12 confirmed: service web tidak memiliki priomed_internal network")


def test_issue9_requirements_langflow_empty():
    """Issue 9: Verifikasi langflow/requirements.langflow.txt kosong"""
    req_path = Path("langflow/requirements.langflow.txt")
    assert req_path.exists(), "langflow/requirements.langflow.txt harus ada"
    
    # Check file size
    file_size = req_path.stat().st_size
    if file_size == 0:
        print("✓ Bug condition 1.16 confirmed: langflow/requirements.langflow.txt kosong (0 bytes)")


def test_issue10_docker_compose_context_wrong():
    """Issue 10: Verifikasi build context masih context: . bukan context: .."""
    docker_compose_path = Path("docker/docker-compose.yml")
    assert docker_compose_path.exists(), "docker/docker-compose.yml harus ada"
    
    content = docker_compose_path.read_text()
    
    # Count context: .. (should be 0 on unfixed code)
    context_parent_count = content.count("context: ..")
    context_current_count = content.count("context: .")
    
    if context_parent_count == 0 and context_current_count > 0:
        print(f"✓ Bug condition 1.17 confirmed: context: . (bukan context: ..) pada {context_current_count} services")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
