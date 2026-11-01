/**
 * web/src/lib/apiClient.test.ts
 * 
 * Bug Condition Exploration Property Tests - Task 1 & Task 3.2
 * 
 * These tests verify that when /auth/login returns 401 with invalid credentials,
 * the exact backend error message is returned (not "Sesi habis. Silakan login kembali.")
 * 
 * **Validates: Requirements 2.1, 2.2, 2.3**
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { loginApi, ApiError } from './apiClient'
import { useAuthStore } from './auth'

// Mock fetch globally
global.fetch = vi.fn()

describe('Bug Condition Exploration Tests - Invalid Login Error Message', () => {
  beforeEach(() => {
    // Reset auth store
    useAuthStore.setState({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,
      isLocked: false,
    })
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  // =========================================================================
  // P1: Error message is "Username atau password salah" (from backend)
  // =========================================================================
  describe('P1: Invalid Login Error Message Accuracy - Backend message returned', () => {
    it('P1 - Invalid password returns backend error message "Username atau password salah"', async () => {
      const backendError = 'Username atau password salah'
      
      // Mock /auth/login endpoint returning 401 with backend error
      vi.mocked(global.fetch).mockResolvedValueOnce({
        status: 401,
        ok: false,
        json: async () => ({
          code: 'INVALID_CREDENTIALS',
          message: backendError,
        }),
      } as Response)

      try {
        await loginApi('apt-01', 'wrongpass')
        expect.fail('Should have thrown ApiError')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        const apiError = error as ApiError
        
        // P1: Verify error message matches backend exactly
        expect(apiError.message).toBe(backendError)
        expect(apiError.message).toBe('Username atau password salah')
        expect(apiError.status).toBe(401)
      }
    })

    it('P1 - Invalid username returns backend error message "Username atau password salah"', async () => {
      const backendError = 'Username atau password salah'
      
      // Mock /auth/login endpoint returning 401 with backend error
      vi.mocked(global.fetch).mockResolvedValueOnce({
        status: 401,
        ok: false,
        json: async () => ({
          code: 'INVALID_CREDENTIALS',
          message: backendError,
        }),
      } as Response)

      try {
        await loginApi('nonexistent', 'demo1234')
        expect.fail('Should have thrown ApiError')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        const apiError = error as ApiError
        
        // P1: Verify error message matches backend exactly
        expect(apiError.message).toBe(backendError)
        expect(apiError.message).toBe('Username atau password salah')
        expect(apiError.status).toBe(401)
      }
    })
  })

  // =========================================================================
  // P2: Error message is NOT "Sesi habis. Silakan login kembali."
  // =========================================================================
  describe('P2: Login 401 does NOT return "Sesi habis" message', () => {
    it('P2 - Invalid password does NOT return "Sesi habis. Silakan login kembali." message', async () => {
      const backendError = 'Username atau password salah'
      
      vi.mocked(global.fetch).mockResolvedValueOnce({
        status: 401,
        ok: false,
        json: async () => ({
          code: 'INVALID_CREDENTIALS',
          message: backendError,
        }),
      } as Response)

      try {
        await loginApi('apt-01', 'wrongpass')
        expect.fail('Should have thrown ApiError')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        const apiError = error as ApiError
        
        // P2: Verify "Sesi habis" message is NOT returned
        expect(apiError.message).not.toContain('Sesi habis')
        expect(apiError.message).not.toContain('habis')
        expect(apiError.message).toBe('Username atau password salah')
      }
    })

    it('P2 - Invalid username does NOT return "Sesi habis. Silakan login kembali." message', async () => {
      const backendError = 'Username atau password salah'
      
      vi.mocked(global.fetch).mockResolvedValueOnce({
        status: 401,
        ok: false,
        json: async () => ({
          code: 'INVALID_CREDENTIALS',
          message: backendError,
        }),
      } as Response)

      try {
        await loginApi('nonexistent', 'demo1234')
        expect.fail('Should have thrown ApiError')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        const apiError = error as ApiError
        
        // P2: Verify "Sesi habis" message is NOT returned
        expect(apiError.message).not.toContain('Sesi habis')
        expect(apiError.message).not.toContain('habis')
        expect(apiError.message).toBe('Username atau password salah')
      }
    })
  })

  // =========================================================================
  // P3: No auto-refresh token attempt occurs for /auth/login 401
  // =========================================================================
  describe('P3: Login 401 does NOT trigger auto-refresh token attempt', () => {
    it('P3 - Invalid password does NOT trigger auto-refresh (fetch called exactly once)', async () => {
      const backendError = 'Username atau password salah'
      
      // Mock /auth/login returning 401
      vi.mocked(global.fetch).mockResolvedValueOnce({
        status: 401,
        ok: false,
        json: async () => ({
          code: 'INVALID_CREDENTIALS',
          message: backendError,
        }),
      } as Response)

      try {
        await loginApi('apt-01', 'wrongpass')
      } catch {
        // Expected to throw
      }

      // P3: Verify fetch was called exactly once (no refresh attempt)
      expect(global.fetch).toHaveBeenCalledTimes(1)
      expect(global.fetch).toHaveBeenCalledWith('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: 'apt-01', password: 'wrongpass' }),
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
        skipAuth: true,
      })
    })

    it('P3 - Invalid username does NOT trigger auto-refresh (fetch called exactly once)', async () => {
      const backendError = 'Username atau password salah'
      
      // Mock /auth/login returning 401
      vi.mocked(global.fetch).mockResolvedValueOnce({
        status: 401,
        ok: false,
        json: async () => ({
          code: 'INVALID_CREDENTIALS',
          message: backendError,
        }),
      } as Response)

      try {
        await loginApi('nonexistent', 'demo1234')
      } catch {
        // Expected to throw
      }

      // P3: Verify fetch was called exactly once (no refresh attempt)
      expect(global.fetch).toHaveBeenCalledTimes(1)
      expect(global.fetch).toHaveBeenCalledWith('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username: 'nonexistent', password: 'demo1234' }),
        headers: expect.objectContaining({
          'Content-Type': 'application/json',
        }),
        skipAuth: true,
      })
    })
  })

  // =========================================================================
  // Concrete Test Case 1: Invalid Password
  // =========================================================================
  describe('Concrete Test Case 1: Invalid Password (apt-01 / wrongpass)', () => {
    it('concrete TC1: Invalid password - returns "Username atau password salah", calls fetch once', async () => {
      const backendError = 'Username atau password salah'
      
      vi.mocked(global.fetch).mockResolvedValueOnce({
        status: 401,
        ok: false,
        json: async () => ({
          code: 'INVALID_CREDENTIALS',
          message: backendError,
        }),
      } as Response)

      try {
        await loginApi('apt-01', 'wrongpass')
        expect.fail('Should have thrown ApiError')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        const apiError = error as ApiError
        
        // Verify error message is correct
        expect(apiError.message).toBe('Username atau password salah')
        expect(apiError.message).not.toContain('Sesi habis')
        expect(apiError.status).toBe(401)
        
        // Verify fetch was called exactly once (no refresh attempt)
        expect(global.fetch).toHaveBeenCalledTimes(1)
      }
    })
  })

  // =========================================================================
  // Concrete Test Case 2: Invalid Username
  // =========================================================================
  describe('Concrete Test Case 2: Invalid Username (nonexistent / demo1234)', () => {
    it('concrete TC2: Invalid username - returns "Username atau password salah", calls fetch once', async () => {
      const backendError = 'Username atau password salah'
      
      vi.mocked(global.fetch).mockResolvedValueOnce({
        status: 401,
        ok: false,
        json: async () => ({
          code: 'INVALID_CREDENTIALS',
          message: backendError,
        }),
      } as Response)

      try {
        await loginApi('nonexistent', 'demo1234')
        expect.fail('Should have thrown ApiError')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiError)
        const apiError = error as ApiError
        
        // Verify error message is correct
        expect(apiError.message).toBe('Username atau password salah')
        expect(apiError.message).not.toContain('Sesi habis')
        expect(apiError.status).toBe(401)
        
        // Verify fetch was called exactly once (no refresh attempt)
        expect(global.fetch).toHaveBeenCalledTimes(1)
      }
    })
  })

  // =========================================================================
  // Valid Login Success (sanity check - should still work)
  // =========================================================================
  describe('Valid Login Success - Sanity Check', () => {
    it('valid login returns tokens and user info without error', async () => {
      const mockResponse = {
        access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwidXNlcm5hbWUiOiJhcHQtMDEiLCJyb2xlIjoiUEhBUk1BQ0lTVCIsImFjdG9yX3R5cGUiOiJQSEFSTUFDSVNUIiwiZXhwIjo5OTk5OTk5OTk5fQ.signature',
        refresh_token: 'refresh_token_123',
        token_type: 'bearer',
        role: 'PHARMACIST',
        username: 'apt-01',
        user_id: '1234567890',
      }

      vi.mocked(global.fetch).mockResolvedValueOnce({
        status: 200,
        ok: true,
        json: async () => mockResponse,
      } as Response)

      const result = await loginApi('apt-01', 'demo1234')

      expect(result.access_token).toBe(mockResponse.access_token)
      expect(result.refresh_token).toBe(mockResponse.refresh_token)
      expect(result.username).toBe('apt-01')
      expect(result.role).toBe('PHARMACIST')
    })
  })
})
