"""Simple seed script untuk testing"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from api.db.session import session_scope, engine
from api.db.models import Base, User, Encounter
from api.auth.password import hash_password
from datetime import datetime, timezone
import uuid

# Create tables
Base.metadata.create_all(engine)

print("Seeding database...")

with session_scope() as session:
    # Check if users exist
    existing = session.query(User).count()
    if existing == 0:
        # Create users
        users = [
            User(
                id="user-apoteker-001",
                username="apoteker1",
                full_name="Apt. Sari Dewi, S.Farm.",
                role="PHARMACIST",
                hashed_password=hash_password("demo1234"),
                is_active=True,
            ),
            User(
                id="user-ttk-001",
                username="ttk1",
                full_name="Ahmad TTK",
                role="TECHNICIAN",
                hashed_password=hash_password("demo1234"),
                is_active=True,
            ),
            User(
                id="user-admin-001",
                username="admin",
                full_name="Admin PrioMed",
                role="ADMIN",
                hashed_password=hash_password("admin1234"),
                is_active=True,
            ),
        ]
        session.add_all(users)
        print(f"  Created {len(users)} users")
    
    # Check if encounters exist
    existing_enc = session.query(Encounter).count()
    if existing_enc == 0:
        # Create some test encounters
        encounters = []
        for i in range(10):
            enc = Encounter(
                id=str(uuid.uuid4()),
                patient_id=f"PAT-{i:04d}",
                patient_name=f"Pasien {i+1}",
                ward="ICU" if i < 3 else "MEDICAL",
                workflow_status="MENUNGGU_TELAAH",
                latest_tier="HIGH" if i < 3 else "MEDIUM",
                ml_score=0.9 if i < 3 else 0.6,
                admitted_at=datetime.now(timezone.utc).isoformat(),
            )
            encounters.append(enc)
        
        session.add_all(encounters)
        print(f"  Created {len(encounters)} encounters")
    
    session.commit()

print("Seeding complete!")
print("\nAkun demo:")
print("  apoteker1 / demo1234  (PHARMACIST)")
print("  ttk1 / demo1234       (TECHNICIAN)")
print("  admin / admin1234     (ADMIN)")
