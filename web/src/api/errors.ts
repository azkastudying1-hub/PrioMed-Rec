/**
 * web/src/api/errors.ts
 * ----------------------
 * Translates HTTP/network errors to user-friendly Indonesian messages.
 */

export interface AppError {
  code: string
  message: string
  isRetryable: boolean
}

export function parseApiError(status: number, detail: string): AppError {
  // Network errors
  if (status === 0) {
    return {
      code: 'NETWORK_ERROR',
      message: 'Koneksi ke server terputus. Periksa jaringan dan coba lagi.',
      isRetryable: true,
    }
  }

  // Authentication
  if (status === 401) {
    return {
      code: 'AUTH_ERROR',
      message: 'Sesi tidak valid atau tidak memiliki akses. Hubungi administrator.',
      isRetryable: false,
    }
  }

  // Validation errors
  if (status === 422) {
    const fieldMatch = detail.match(/field: (\w+)/i)
    if (fieldMatch) {
      return {
        code: 'VALIDATION_ERROR',
        message: `Data tidak valid pada kolom: ${fieldMatch[1]}. Periksa isian form.`,
        isRetryable: false,
      }
    }
    if (detail.includes('medication')) {
      return {
        code: 'VALIDATION_ERROR',
        message: 'Nama obat tidak boleh kosong. Pastikan semua obat memiliki nama.',
        isRetryable: false,
      }
    }
    return {
      code: 'VALIDATION_ERROR',
      message: 'Data yang dimasukkan tidak valid. Periksa kembali isian form.',
      isRetryable: false,
    }
  }

  // Not found
  if (status === 404) {
    if (detail.includes('patient') || detail.includes('BPMH')) {
      return {
        code: 'NOT_FOUND',
        message: 'Data pasien tidak ditemukan. Pastikan ID pasien benar.',
        isRetryable: false,
      }
    }
    return {
      code: 'NOT_FOUND',
      message: 'Data tidak ditemukan.',
      isRetryable: false,
    }
  }

  // LLM errors
  if (status === 503 && detail.includes('LLM')) {
    return {
      code: 'LLM_UNAVAILABLE',
      message: 'Laporan SBAR tidak dapat dibuat saat ini. Data struktural tetap tersedia untuk review.',
      isRetryable: true,
    }
  }

  // Server errors
  if (status >= 500) {
    const errCode = detail.match(/\b([A-Z_]{4,})\b/)?.[1] || 'ERR500'
    return {
      code: 'SERVER_ERROR',
      message: `Terjadi kesalahan sistem. Hubungi administrator dengan kode: ${errCode}`,
      isRetryable: true,
    }
  }

  // Default
  return {
    code: 'UNKNOWN_ERROR',
    message: 'Terjadi kesalahan tidak dikenal. Coba lagi atau hubungi administrator.',
    isRetryable: true,
  }
}

// Retry with exponential backoff
export async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries = 3,
  onRetry?: (attempt: number) => void,
): Promise<T> {
  let lastError: Error | null = null
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn()
    } catch (err) {
      lastError = err as Error
      if (attempt < maxRetries - 1) {
        const waitMs = 1000 * Math.pow(2, attempt) // 1s, 2s, 4s
        onRetry?.(attempt + 1)
        await new Promise(resolve => setTimeout(resolve, waitMs))
      }
    }
  }
  throw lastError!
}
