"""Check database schema for foreign keys"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import sqlalchemy as sa
from api.db.session import engine

inspector = sa.inspect(engine)

print("=" * 60)
print("Foreign Keys in queue_entries table")
print("=" * 60)

fks = inspector.get_foreign_keys('queue_entries')
for fk in fks:
    print(f"  {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")

print("\n" + "=" * 60)
print("Foreign Keys in encounters table")
print("=" * 60)

fks = inspector.get_foreign_keys('encounters')
for fk in fks:
    print(f"  {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
