"""
simulator — Hospital Simulator untuk PrioMed-Rec

Mensimulasikan lingkungan rumah sakit skala nyata untuk demo dan uji beban.
Antrean benar-benar bergerak: pasien datang, TTK mengisi BPMH, apoteker
mengambil kasus, ada transfer/lab kritis/pulang mendadak.

LABEL WAJIB:
  "Data simulasi — parameter berbasis asumsi, belum dikalibrasi dengan RS"

Gunakan:
  python -m simulator.run --size M --speed 60 --scenario evening_surge --seed 42

Q-007 (PRIOMEDREC_QUEUE_MANAGEMENT_PLAN.md §9)
ADR-20: tidak ada panggilan LLM/Langflow per pasien per tick.
"""
