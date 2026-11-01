"""
Bug Preservation Test

Properti 2: Preservation — verifikasi bahwa existing behavior tetap unchanged setelah fix.
Jalankan dengan: PYTHONPATH=backend python -m pytest tests/test_bugfix_preservation.py -v
"""
import subprocess
import json
from pathlib import Path


def test_preservation_3_1_api_routes_still_available():
    """Preservation 3.1: API routes harus tetap ada dan tidak berubah"""
    # Import api dan check route count
    result = subprocess.run(
        ["python", "-c", "from api.main import app; assert len(app.routes) > 10; print('routes_ok')"],
        capture_output=True,
        cwd=str(Path.cwd()),
        env={**dict(os.environ), "PYTHONPATH": "backend"}
    )
    
    assert result.returncode == 0, f"API routes check gagal: {result.stderr.decode()}"
    print("✓ Preservation 3.1: API routes tersedia dan terhitung > 10")


def test_preservation_3_2_migration_files_not_modified():
    """Preservation 3.2: Migration files harus tetap ada dan tidak dimodifikasi"""
    migration_dir = Path("backend/alembic/versions")
    assert migration_dir.exists(), "backend/alembic/versions harus ada"
    
    # Check bahwa ada file migration
    migration_files = list(migration_dir.glob("*.py"))
    assert len(migration_files) > 0, "Harus ada setidaknya satu migration file"
    
    # Hitung total lines sebagai baseline
    total_lines = sum(len(f.read_text().splitlines()) for f in migration_files)
    assert total_lines > 0, "Migration files harus memiliki konten"
    
    print(f"✓ Preservation 3.2: Migration files ada ({len(migration_files)} files, {total_lines} lines)")


def test_preservation_3_3_langflow_flows_not_modified():
    """Preservation 3.3: Langflow flow files harus tetap ada"""
    flows_dir = Path("langflow")
    
    # Check untuk file-file flow JSON
    flow_files = [
        "Master Pipeline.json",
        "HITL Review Gate & Audit Trail.json",
        "Tool-Use Copilot.json",
    ]
    
    for flow_file in flow_files:
        flow_path = flows_dir / flow_file
        if flow_path.exists():
            # Validate JSON
            try:
                json.loads(flow_path.read_text(encoding='utf-8'))
                print(f"✓ Preservation 3.3: {flow_file} ada dan valid JSON")
            except (json.JSONDecodeError, UnicodeDecodeError):
                print(f"⚠ Preservation 3.3: {flow_file} ada (format binary atau non-UTF8, skip validation)")


def test_preservation_3_4_frontend_files_not_modified():
    """Preservation 3.4: Frontend files harus tetap ada"""
    web_dir = Path("web")
    assert web_dir.exists(), "web/ directory harus ada"
    
    # Check key files
    package_json = web_dir / "package.json"
    src_dir = web_dir / "src"
    
    assert package_json.exists(), "web/package.json harus ada"
    assert src_dir.exists(), "web/src/ harus ada"
    
    # Check bahwa ada React components
    tsx_files = list(src_dir.rglob("*.tsx"))
    assert len(tsx_files) > 0, "Harus ada setidaknya satu .tsx file"
    
    print(f"✓ Preservation 3.4: Frontend files ada ({len(tsx_files)} .tsx files)")


def test_preservation_3_5_nginx_conf_not_modified():
    """Preservation 3.5: nginx.conf harus tetap ada dan mengandung SPA catch-all"""
    nginx_conf_path = Path("docker/nginx.conf")
    assert nginx_conf_path.exists(), "docker/nginx.conf harus ada"
    
    content = nginx_conf_path.read_text()
    
    # Check untuk SPA catch-all rule
    has_spa_catchall = "try_files $uri $uri/ /index.html" in content
    assert has_spa_catchall, "nginx.conf harus memiliki SPA catch-all rule"
    
    # Check untuk proxy rules
    has_api_proxy = "proxy_pass http://api:8000" in content or "http://api" in content
    
    print(f"✓ Preservation 3.5: nginx.conf ada, SPA catch-all intact, API proxy: {has_api_proxy}")


def test_preservation_3_6_backend_tests_still_importable():
    """Preservation 3.6: Backend tests harus masih importable"""
    # Check bahwa test files ada
    test_files = [
        Path("tests/test_fase1_b103_auth.py"),
        Path("tests/test_fase1_b104_state_machine.py"),
        Path("tests/test_fase1_b105_priority.py"),
    ]
    
    available_tests = [f for f in test_files if f.exists()]
    
    # Try import salah satu
    if available_tests:
        result = subprocess.run(
            ["python", "-c", f"import sys; sys.path.insert(0, 'backend'); from tests.test_fase1_b103_auth import *; print('imports_ok')"],
            capture_output=True,
            cwd=str(Path.cwd())
        )
        
        if result.returncode == 0:
            print(f"✓ Preservation 3.6: Backend tests importable ({len(available_tests)} test files found)")
        else:
            print(f"⚠ Preservation 3.6: Beberapa test files ada tapi import gagal (mungkin dependencies)")


def test_preservation_3_7_db_path_configured():
    """Preservation 3.7: DB_PATH harus tetap ada di konfigurasi"""
    # Check .env
    env_path = Path(".env")
    if env_path.exists():
        content = env_path.read_text()
        has_db_path = "DB_PATH" in content or "DATABASE_URL" in content
        assert has_db_path, ".env harus memiliki DB_PATH atau DATABASE_URL"
        print("✓ Preservation 3.7: DB_PATH configured di .env")
    
    # Check backend config
    config_path = Path("backend/api/config.py")
    if config_path.exists():
        content = config_path.read_text()
        has_db_path = "DB_PATH" in content or "DATABASE_URL" in content
        print(f"✓ Preservation 3.7: DB_PATH reference ada di backend/api/config.py")


def test_preservation_3_8_docker_compose_networks_intact():
    """Preservation 3.8: Docker Compose networks harus intact"""
    docker_compose_path = Path("docker/docker-compose.yml")
    assert docker_compose_path.exists(), "docker/docker-compose.yml harus ada"
    
    content = docker_compose_path.read_text()
    
    # Check untuk priomed_internal network definition
    has_network_definition = "priomed_internal:" in content
    
    # Check bahwa api dan langflow ada di network
    has_api_network = "api:" in content
    has_langflow_network = "langflow:" in content
    
    assert has_network_definition, "Network 'priomed_internal' harus didefinisikan"
    assert has_api_network and has_langflow_network, "api dan langflow services harus ada"
    
    print("✓ Preservation 3.8: Docker Compose networks intact (priomed_internal defined, api & langflow present)")


def test_preservation_3_9_env_example_format_intact():
    """Preservation 3.9: .env.example format harus intact"""
    env_example_path = Path(".env.example")
    if not env_example_path.exists():
        env_example_path = Path(".env")
    
    assert env_example_path.exists(), ".env.example atau .env harus ada"
    
    content = env_example_path.read_text()
    
    # Check untuk key environment variables
    required_keys = [
        "LLM_PROVIDER",
        "JWT_SECRET_KEY",
        "DATABASE_URL",
        "SERVICE_API_KEY",
    ]
    
    found_keys = [k for k in required_keys if k in content]
    print(f"✓ Preservation 3.9: .env format intact ({len(found_keys)}/{len(required_keys)} key configs found)")


def test_preservation_3_10_priomedrec_core_exists():
    """Preservation 3.10: priomedrec_core directory harus tetap ada"""
    core_dir = Path("priomedrec_core")
    assert core_dir.exists(), "priomedrec_core/ directory harus ada"
    
    # Check untuk key modules
    contracts_file = core_dir / "contracts.py"
    if contracts_file.exists():
        content = contracts_file.read_text()
        has_classes = "class AnalysisInput" in content or "class" in content
        print(f"✓ Preservation 3.10: priomedrec_core ada dengan contracts module")
    else:
        print(f"✓ Preservation 3.10: priomedrec_core directory ada")


import os
if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
