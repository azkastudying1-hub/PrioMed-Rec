"""Sinkronkan `workflow_status` encounter dengan state antrean (data simulasi).

Latar masalah
-------------
Sebagian data seed lama membuat `queue_entries` bertipe REVIEW tanpa memajukan
`workflow_status` encounter, sehingga Case Workspace menampilkan
"Menunggu BPMH" padahal pasien sudah berada di antrean telaah.

Aturan sinkronisasi
-------------------
- REVIEW / OPEN     -> MENUNGGU_TELAAH
- REVIEW / CLAIMED  -> DRAFT_REVIEW

Hanya mengisi status yang masih "belum masuk telaah"
(MENUNGGU_BPMH / MENUNGGU_REVIEW) sehingga status yang sudah final
(SELESAI_APPROVE, DITOLAK, dst.) tidak pernah ditimpa.

Idempoten: aman dijalankan berulang.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from api.db.session import session_scope

_SYNC_TELAAH = text(
    """
    UPDATE encounters
       SET workflow_status = 'MENUNGGU_TELAAH'
     WHERE workflow_status IN ('MENUNGGU_BPMH', 'MENUNGGU_REVIEW')
       AND id IN (SELECT encounter_id FROM queue_entries
                   WHERE queue_type = 'REVIEW' AND state = 'OPEN')
    """
)

_SYNC_DRAFT = text(
    """
    UPDATE encounters
       SET workflow_status = 'DRAFT_REVIEW'
     WHERE workflow_status IN ('MENUNGGU_BPMH', 'MENUNGGU_REVIEW')
       AND id IN (SELECT encounter_id FROM queue_entries
                   WHERE queue_type = 'REVIEW' AND state = 'CLAIMED')
    """
)


def main() -> None:
    with session_scope() as session:
        synced_telaah = session.execute(_SYNC_TELAAH).rowcount
        synced_draft = session.execute(_SYNC_DRAFT).rowcount
        session.commit()

        remaining = session.execute(
            text(
                "SELECT workflow_status, COUNT(*) FROM encounters "
                "GROUP BY 1 ORDER BY 2 DESC"
            )
        ).all()

    print(f"Synced MENUNGGU_TELAAH={synced_telaah}, DRAFT_REVIEW={synced_draft}")
    print("workflow_status:", ", ".join(f"{row[0]}={row[1]}" for row in remaining))


if __name__ == "__main__":
    main()
