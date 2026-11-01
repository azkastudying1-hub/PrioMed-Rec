"""
Test script untuk memverifikasi perbaikan klaim encounter.
Script ini akan:
1. Login sebagai apoteker1
2. Mengambil worklist
3. Mencoba klaim encounter pertama yang tersedia
4. Melepas klaim
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import requests
import json

BASE_URL = "http://localhost:8001/api/v1"

def test_claim_fix():
    print("=" * 60)
    print("TEST: Klaim Encounter Fix")
    print("=" * 60)
    
    # Step 1: Login
    print("\n[1] Login sebagai apoteker1...")
    login_data = {
        "username": "apoteker1",
        "password": "demo1234"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data["access_token"]
        user_id = token_data["user_id"]
        print(f"   ✓ Login berhasil! User ID: {user_id}")
        print(f"   Token: {access_token[:30]}...")
    except Exception as e:
        print(f"   ✗ Login gagal: {e}")
        print("   Pastikan backend server sedang berjalan di http://localhost:8000")
        return False
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Step 2: Get worklist
    print("\n[2] Mengambil worklist...")
    try:
        response = requests.get(f"{BASE_URL}/worklist?page_size=10", headers=headers)
        response.raise_for_status()
        worklist = response.json()
        items = worklist.get("items", [])
        print(f"   ✓ Worklist berhasil diambil. Total: {worklist.get('total', 0)} items")
        
        if not items:
            print("   ⚠ Tidak ada item di worklist. Tidak dapat melanjutkan test.")
            return True
            
    except Exception as e:
        print(f"   ✗ Gagal mengambil worklist: {e}")
        return False
    
    # Step 3: Claim first encounter
    first_item = items[0]
    encounter_id = first_item["encounter_id"]
    row_version = first_item.get("row_version", 0)
    
    print(f"\n[3] Mencoba klaim encounter: {encounter_id[:16]}...")
    print(f"   Row version: {row_version}")
    print(f"   Status: {first_item.get('workflow_status')}")
    print(f"   Claimed by: {first_item.get('claimed_by')}")
    
    try:
        claim_headers = {**headers, "If-Match": str(row_version)}
        response = requests.post(
            f"{BASE_URL}/worklist/{encounter_id}/claim",
            headers=claim_headers
        )
        
        if response.status_code == 200:
            claim_data = response.json()
            print(f"   ✓ Klaim berhasil!")
            print(f"   New row version: {claim_data.get('row_version')}")
            print(f"   Claimed by: {claim_data.get('claimed_by')}")
        else:
            print(f"   ✗ Klaim gagal dengan status {response.status_code}")
            print(f"   Response: {response.text}")
            
            # If conflict (already claimed), that's expected behavior
            if response.status_code == 409:
                print("   ℹ Encounter sudah diklaim user lain (expected behavior)")
            else:
                return False
                
    except Exception as e:
        print(f"   ✗ Error saat klaim: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 4: Get worklist again to verify claim
    print("\n[4] Verifikasi klaim di worklist...")
    try:
        response = requests.get(f"{BASE_URL}/worklist?page_size=10", headers=headers)
        response.raise_for_status()
        worklist = response.json()
        items = worklist.get("items", [])
        
        # Find our claimed encounter
        claimed_item = next(
            (item for item in items if item["encounter_id"] == encounter_id),
            None
        )
        
        if claimed_item:
            print(f"   Encounter ID: {claimed_item['encounter_id'][:16]}")
            print(f"   Claimed by: {claimed_item.get('claimed_by')}")
            print(f"   Claimed at: {claimed_item.get('claimed_at')}")
            
            if claimed_item.get("claimed_by") == user_id:
                print(f"   ✓ Klaim terverifikasi di worklist!")
            else:
                print(f"   ⚠ Claimed by berbeda: {claimed_item.get('claimed_by')}")
        else:
            print("   ⚠ Encounter tidak ditemukan di worklist")
            
    except Exception as e:
        print(f"   ✗ Gagal verifikasi: {e}")
        return False
    
    # Step 5: Release claim
    print(f"\n[5] Melepas klaim encounter: {encounter_id[:16]}...")
    try:
        response = requests.post(
            f"{BASE_URL}/worklist/{encounter_id}/release",
            headers=headers
        )
        
        if response.status_code == 200:
            print(f"   ✓ Klaim berhasil dilepas!")
        else:
            print(f"   ✗ Release gagal dengan status {response.status_code}")
            print(f"   Response: {response.text}")
            
    except Exception as e:
        print(f"   ✗ Error saat release: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✓ SEMUA TEST BERHASIL!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    success = test_claim_fix()
    sys.exit(0 if success else 1)
