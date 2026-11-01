"""Debug claim error"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from api.db.session import session_scope
from api.db.models import Encounter, User
from api.services.audit_service import append_audit
from datetime import datetime, timezone
import traceback

encounter_id = "4a8f05e5-3267-4b0c-a6ba-9dd7931a0b3a"
user_id = "user-apoteker-001"

print(f"Testing claim for encounter {encounter_id}...")
print(f"User ID: {user_id}")

try:
    with session_scope() as session:
        # Check encounter
        enc = session.query(Encounter).filter(Encounter.id == encounter_id).first()
        if not enc:
            print(f"ERROR: Encounter not found!")
            sys.exit(1)
        
        print(f"\nEncounter found:")
        print(f"  ID: {enc.id}")
        print(f"  Patient: {enc.patient_name}")
        print(f"  Status: {enc.workflow_status}")
        print(f"  Claimed by: {enc.claimed_by}")
        print(f"  Row version: {enc.row_version}")
        
        # Check user
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            print(f"ERROR: User not found!")
            sys.exit(1)
        
        print(f"\nUser found:")
        print(f"  ID: {user.id}")
        print(f"  Username: {user.username}")
        print(f"  Role: {user.role}")
        
        # Try to update claim
        print(f"\nAttempting to update claim...")
        now = datetime.now(timezone.utc).isoformat()
        enc.claimed_by = user_id
        enc.claimed_at = now
        enc.row_version = (enc.row_version or 0) + 1
        enc.updated_at = now
        
        print(f"  Set claimed_by = {user_id}")
        print(f"  Set claimed_at = {now}")
        print(f"  Set row_version = {enc.row_version}")
        
        # Try to add audit
        print(f"\nAdding audit entry...")
        append_audit(
            session,
            action="CLAIM",
            actor_id=user_id,
            actor_type="human",
            encounter_id=encounter_id,
        )
        
        # Try to commit
        print(f"\nCommitting transaction...")
        session.commit()
        print(f"✓ SUCCESS! Claim committed successfully.")
        
except Exception as e:
    print(f"\n✗ ERROR: {type(e).__name__}: {e}")
    print(f"\nTraceback:")
    traceback.print_exc()
