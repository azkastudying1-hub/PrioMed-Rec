import type {
  AuditEntry,
  HighAlertMedication,
  Patient,
  WardCapacity,
} from "../types/clinical"

const baseMedications = [
  {
    id: "m1",
    name: "Warfarin",
    dose: "2",
    unit: "mg",
    frequency: "1× sehari",
    route: "Oral",
    source: "Wawancara pasien",
    disposition: "Dilanjutkan" as const,
    reason: "Riwayat fibrilasi atrium",
  },
  {
    id: "m2",
    name: "Metformin",
    dose: "500",
    unit: "mg",
    frequency: "2× sehari",
    route: "Oral",
    source: "Daftar obat keluarga",
    disposition: "Ditunda" as const,
    reason: "Menunggu evaluasi fungsi ginjal",
  },
  {
    id: "m3",
    name: "Amlodipine",
    dose: "5",
    unit: "mg",
    frequency: "1× sehari",
    route: "Oral",
    source: "Resep terakhir",
    disposition: "Dilanjutkan" as const,
    reason: "",
  },
]

const completePatient: Patient = {
  id: "Pasien #0231",
  admissionId: "ADM-240231",
  ward: "ICU",
  age: 72,
  admittedAt: "Hari ini, 06:42",
  riskScore: 0.87,
  riskLevel: "HIGH",
  status: "Perlu verifikasi",
  highAlertCount: 3,
  topReason: "Usia lanjut, 9 order admisi, dan 3 obat high-alert",
  contributions: [
    {
      label: "Jumlah order admisi",
      value: 0.24,
      detail: "9 order tercatat saat admisi",
    },
    { label: "Obat high-alert", value: 0.19, detail: "3 order high-alert" },
    { label: "Usia", value: 0.13, detail: "72 tahun" },
    {
      label: "Kunjungan 12 bulan",
      value: 0.08,
      detail: "4 kunjungan sebelumnya",
    },
    {
      label: "Bangsal admisi",
      value: -0.05,
      detail: "Kontribusi relatif ICU pada model demo",
    },
  ],
  medications: baseMedications,
  discrepancies: [
    {
      id: "d1",
      type: "POTENTIAL_UNDOCUMENTED_OMISSION",
      medication: "Warfarin 2 mg",
      home: "Tercatat 1× sehari",
      admission: "Tidak ditemukan pada order admisi",
      reason:
        "Obat rumah tidak memiliki padanan pada order admisi dan belum ada alasan penghentian.",
      status: "Perlu konfirmasi",
    },
    {
      id: "d2",
      type: "POSSIBLE_SUBSTITUTION",
      medication: "Amlodipine → Nifedipine",
      home: "Amlodipine 5 mg 1× sehari",
      admission: "Nifedipine 30 mg 1× sehari",
      reason:
        "Kelas terapi serupa terdeteksi, tetapi maksud substitusi belum terdokumentasi.",
      status: "Perlu konfirmasi",
    },
    {
      id: "d3",
      type: "POTENTIAL_DUPLICATION",
      medication: "Paracetamol / Acetaminophen",
      home: "Paracetamol 500 mg bila perlu",
      admission: "Acetaminophen 500 mg + Paracetamol 500 mg",
      reason: "Dua nama obat dinormalisasi ke kandungan aktif yang sama.",
      status: "Perlu konfirmasi",
    },
    {
      id: "d4",
      type: "UNRESOLVED_MATCH",
      medication: "“Ins. rapid”",
      home: "Catatan keluarga: Ins. rapid 6 unit",
      admission: "Insulin aspart sliding scale",
      reason: "Singkatan pada sumber BPMH belum dapat dipadankan secara pasti.",
      status: "Perlu konfirmasi",
    },
  ],
  interactions: [
    {
      id: "i1",
      drugs: "Warfarin + Amiodarone",
      severity: "Tinggi",
      reason:
        "Potensi peningkatan efek antikoagulan pada penggunaan bersamaan.",
      monitoring:
        "Verifikasi indikasi, waktu mulai, dan parameter INR pada referensi institusi.",
      source: "Basis pengetahuan demo · monograf interaksi v0.3",
      sourceUrl: "https://www.micromedexsolutions.com/",
      status: "NEEDS_PHARMACIST_REVIEW",
    },
  ],
  sbar: {
    situation:
      "Pasien admisi ICU dengan skor prioritas 0,87 (HIGH) dan empat kandidat ketidaksesuaian obat.",
    background:
      "BPMH demo memuat warfarin, metformin, dan amlodipine. Terdapat tiga order high-alert saat admisi.",
    assessment:
      "Rule engine menandai kandidat omission warfarin, kemungkinan substitusi antihipertensi, potensi duplikasi paracetamol, dan satu padanan obat yang belum terselesaikan.",
    recommendation:
      "Apakah dokter dapat mengonfirmasi maksud penghentian warfarin, substitusi antihipertensi, dan kebutuhan dua order paracetamol sebelum dokumentasi difinalkan?",
  },
}

const patientSeeds: Array<[string, string, number, number, Patient["riskLevel"], Patient["status"], number, string]> =
  [
    [
      "Pasien #0184",
      "HCU",
      68,
      0.79,
      "HIGH",
      "Menunggu BPMH",
      2,
      "2 obat high-alert dan 8 order admisi",
    ],
    [
      "Pasien #0412",
      "Penyakit Dalam",
      61,
      0.68,
      "MEDIUM",
      "Siap dianalisis",
      1,
      "Polifarmasi pada order admisi",
    ],
    [
      "Pasien #0307",
      "Kardiologi",
      75,
      0.64,
      "MEDIUM",
      "Perlu verifikasi",
      2,
      "Usia lanjut dan kunjungan berulang",
    ],
    [
      "Pasien #0109",
      "Bedah",
      54,
      0.58,
      "MEDIUM",
      "Menunggu BPMH",
      1,
      "Riwayat admisi dalam 30 hari",
    ],
    [
      "Pasien #0528",
      "Neurologi",
      66,
      0.53,
      "MEDIUM",
      "Siap dianalisis",
      0,
      "Jumlah order admisi di atas rerata",
    ],
    [
      "Pasien #0147",
      "Penyakit Dalam",
      48,
      0.45,
      "MEDIUM",
      "Disetujui",
      1,
      "Satu order high-alert",
    ],
    [
      "Pasien #0602",
      "Bedah",
      39,
      0.34,
      "LOW",
      "Menunggu BPMH",
      0,
      "Tiga order admisi",
    ],
    [
      "Pasien #0276",
      "Kardiologi",
      57,
      0.3,
      "LOW",
      "Disetujui",
      0,
      "Tidak ada faktor dominan",
    ],
    [
      "Pasien #0395",
      "Neurologi",
      44,
      0.24,
      "LOW",
      "Ditolak",
      0,
      "Kontribusi model rendah",
    ],
  ]

export const initialPatients: Patient[] = [
  completePatient,
  ...patientSeeds.map(
    ([id, ward, age, score, level, status, highAlert, reason], index) => ({
      ...completePatient,
      id,
      admissionId: `ADM-24${String(184 + index * 37).padStart(4, "0")}`,
      ward,
      age,
      riskScore: score,
      riskLevel: level,
      status,
      highAlertCount: highAlert,
      topReason: reason,
      interactions: index === 1 ? [] : completePatient.interactions,
      discrepancies:
        index % 2 === 0
          ? completePatient.discrepancies.slice(0, 2)
          : completePatient.discrepancies.slice(2),
    }),
  ),
]

export const initialAuditEntries: AuditEntry[] = [
  {
    id: "a1",
    patientId: "Pasien #0147",
    action: "APPROVE",
    pharmacist: "Apt. Maya R.",
    timestamp: "Hari ini, 09:18",
    note: "BPMH dan order admisi telah diverifikasi.",
    source: "Keputusan apoteker",
  },
  {
    id: "a2",
    patientId: "Pasien #0395",
    action: "REJECT",
    pharmacist: "Apt. Dimas A.",
    timestamp: "Hari ini, 08:44",
    note: "Data sumber belum cukup; dikembalikan untuk verifikasi.",
    source: "Keputusan apoteker",
  },
  {
    id: "a3",
    patientId: "Pasien #0307",
    action: "EDIT",
    pharmacist: "Apt. Maya R.",
    timestamp: "Kemarin, 16:12",
    note: "Koreksi frekuensi obat dari resep terakhir.",
    source: "Edit manual",
  },
]

export const initialHighAlertMedications: HighAlertMedication[] = [
  {
    id: "h1",
    name: "Insulin",
    category: "Hipoglikemik",
    source: "Daftar RS demo",
    version: "2025.1",
    verified: true,
  },
  {
    id: "h2",
    name: "Warfarin",
    category: "Antikoagulan",
    source: "Daftar RS demo",
    version: "2025.1",
    verified: true,
  },
  {
    id: "h3",
    name: "Heparin",
    category: "Antikoagulan",
    source: "ISMP adaptasi demo",
    version: "2025.1",
    verified: false,
  },
  {
    id: "h4",
    name: "Kalium klorida konsentrat",
    category: "Elektrolit",
    source: "Daftar RS demo",
    version: "2025.1",
    verified: true,
  },
]

export const initialWardCapacities: WardCapacity[] = [
  { ward: "ICU", capacity: 8, allocated: 5 },
  { ward: "HCU", capacity: 6, allocated: 4 },
  { ward: "Penyakit Dalam", capacity: 12, allocated: 9 },
  { ward: "Kardiologi", capacity: 8, allocated: 6 },
  { ward: "Bedah", capacity: 10, allocated: 4 },
  { ward: "Neurologi", capacity: 7, allocated: 3 },
]
