"""
Test LLM fallback behavior when API key is not configured.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_llm_service_empty_api_key():
    """Test that empty API key returns proper error code."""
    from src.llm.service import _call_llm
    
    with patch.dict('os.environ', {
        'LLM_PROVIDER': '',
        'LLM_API_KEY': '',
        'LLM_MODEL_NAME': '',
    }, clear=True):
        try:
            _call_llm("system", "user")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "LLM_API_KEY_NOT_SET" in str(e)


def test_llm_service_placeholder_api_key():
    """Test that placeholder API key is detected and rejected."""
    from src.llm.service import _call_llm
    
    with patch.dict('os.environ', {
        'LLM_PROVIDER': 'groq',
        'LLM_API_KEY': 'gsk_paste_key_disini',
        'LLM_MODEL_NAME': 'llama-3.3-70b-versatile',
    }, clear=True):
        try:
            _call_llm("system", "user")
            assert False, "Should have raised RuntimeError"
        except RuntimeError as e:
            assert "LLM_API_KEY_PLACEHOLDER" in str(e)


def test_analyze_endpoint_without_llm():
    """Test that /analyze endpoint works without LLM configured."""
    from fastapi.testclient import TestClient
    from api.main import app
    
    client = TestClient(app)
    
    # Mock patient resolver to return test data
    with patch('api.services.patient_service.get_patient_context') as mock_resolver:
        mock_resolver.return_value = {
            'patient_id': 'P001',
            'encounter_id': 'E001',
            'feature_vector': {
                'age': 65,
                'gender_encoded': 1,
                'polypharmacy_flag': 1,
                'high_alert_flag': 0,
                'allergy_count': 0,
                'active_condition_count': 3,
                'prior_encounter_count': 2,
            },
            'pre_admission_meds': [],
            'admission_meds': [],
            'encounter_meta': {
                'age': 65,
                'encounter_class': 'IMP',
                'encounter_start': '2024-01-01',
            },
        }
        
        response = client.post('/analyze', json={
            'patient_id': 'P001',
        })
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have basic structure even without LLM
        assert 'patient_id' in data
        assert 'encounter_id' in data
        assert 'discrepancy_likelihood' in data
        assert 'review_priority' in data
        assert 'flags' in data
        assert 'report' in data
        
        # Report should exist (fallback or LLM)
        assert len(data['report']) > 0
        
        # report_available should be False when LLM not configured
        assert data['report_available'] == False


def test_analyze_handles_undefined_response():
    """Test that analyzePatient handles undefined/null responses."""
    # This would be tested in frontend with integration tests
    # Here we just verify the backend returns proper structure
    from fastapi.testclient import TestClient
    from api.main import app
    
    client = TestClient(app)
    
    # Test with invalid patient_id
    response = client.post('/analyze', json={
        'patient_id': 'NONEXISTENT_PATIENT',
    })
    
    # Should return 404, not 500
    assert response.status_code == 404


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
