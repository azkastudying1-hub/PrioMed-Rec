/**
 * web/src/components/CopilotDrawer.tsx
 * ----------------------------------------
 * Copilot AI Drawer — A-304, F-214
 *
 * Slide-in panel (right) for asking the AI Copilot about the current case.
 * All calls go through AI Gateway: UI → POST /api/v1/ai/copilot → FastAPI (ADR-02, S7).
 *
 * Label "Draf AI — wajib diverifikasi apoteker" always visible (S12).
 * Browser NEVER calls Langflow or LLM directly.
 */

import { useState, useRef, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { AiDraftLabel } from './AiDraftLabel'
import { askCopilot, type CopilotResponse } from '../api/langflow'

interface Message {
  id: string
  role: 'user' | 'assistant'
  text: string
  source?: string
  warnings?: string[]
  timestamp: Date
}

interface Props {
  encounterId?: string
  isOpen: boolean
  onClose: () => void
}

export function CopilotDrawer({ encounterId, isOpen, onClose }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputText, setInputText] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Scroll to bottom when new message arrives
  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages])

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [isOpen])

  const askMutation = useMutation<CopilotResponse, Error, string>({
    mutationFn: (question: string) =>
      askCopilot(question, encounterId, encounterId ? { encounter_id: encounterId } : undefined),
    onMutate: (question) => {
      // Optimistically add user message
      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: 'user',
        text: question,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, userMsg])
      setInputText('')
    },
    onSuccess: (data) => {
      const aiMsg: Message = {
        id: `ai-${Date.now()}`,
        role: 'assistant',
        text: data.answer,
        source: data.source,
        warnings: data.warnings,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, aiMsg])
    },
    onError: (error) => {
      const errMsg: Message = {
        id: `err-${Date.now()}`,
        role: 'assistant',
        text: `Gagal menghubungi AI Copilot: ${error.message}. Silakan coba lagi atau hubungi admin.`,
        source: 'error',
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errMsg])
    },
  })

  function handleSend() {
    const q = inputText.trim()
    if (!q || askMutation.isPending) return
    askMutation.mutate(q)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const QUICK_QUESTIONS = [
    'Apa diskrepansi paling kritis pada kasus ini?',
    'Apakah ada interaksi obat yang perlu diperhatikan?',
    'Mengapa pasien ini mendapat prioritas tinggi?',
    'Obat high-alert apa yang perlu konfirmasi?',
  ]

  if (!isOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-30 bg-black/20"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="AI Copilot"
        className="fixed right-0 top-0 h-full w-full max-w-md z-40 bg-white shadow-2xl flex flex-col"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">
              🤖 AI Copilot Farmasi
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Tanya tentang kasus ini — jawaban melalui AI Gateway
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition-colors"
            aria-label="Tutup copilot"
          >
            ✕
          </button>
        </div>

        {/* AI Draft Label — always visible (S12) */}
        <div className="px-4 pt-3">
          <AiDraftLabel source="ai-copilot" />
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          {messages.length === 0 && (
            <div className="text-center py-6">
              <p className="text-sm text-slate-500 mb-4">
                Tanyakan apa saja tentang kasus rekonsiliasi obat ini.
              </p>
              <div className="space-y-2">
                {QUICK_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => {
                      setInputText(q)
                      inputRef.current?.focus()
                    }}
                    className="w-full text-left px-3 py-2 text-xs bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg border border-blue-100 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white rounded-br-sm'
                    : msg.source === 'error'
                    ? 'bg-red-50 text-red-700 border border-red-200 rounded-bl-sm'
                    : 'bg-slate-100 text-slate-800 rounded-bl-sm'
                }`}
              >
                <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>
                {msg.role === 'assistant' && msg.source && msg.source !== 'error' && (
                  <p className="text-xs mt-1 opacity-60">
                    Sumber: {msg.source}
                    {msg.warnings && msg.warnings.length > 0 && (
                      <span className="ml-2 text-yellow-600">⚠ {msg.warnings.length} peringatan</span>
                    )}
                  </p>
                )}
                <p className="text-xs mt-1 opacity-40">
                  {msg.timestamp.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
            </div>
          ))}

          {/* Loading indicator */}
          {askMutation.isPending && (
            <div className="flex justify-start">
              <div className="bg-slate-100 rounded-2xl rounded-bl-sm px-4 py-3">
                <div className="flex gap-1 items-center">
                  <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:0ms]" />
                  <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:150ms]" />
                  <div className="w-1.5 h-1.5 bg-slate-400 rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input area */}
        <div className="border-t border-slate-200 px-4 py-3 bg-white">
          <div className="flex gap-2 items-end">
            <textarea
              ref={inputRef}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Tanya tentang kasus ini... (Enter untuk kirim)"
              className="flex-1 px-3 py-2 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none min-h-[44px] max-h-[120px]"
              rows={1}
              disabled={askMutation.isPending}
              aria-label="Pertanyaan untuk AI Copilot"
              maxLength={500}
            />
            <button
              onClick={handleSend}
              disabled={!inputText.trim() || askMutation.isPending}
              className="px-3 py-2 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              aria-label="Kirim pertanyaan"
            >
              {askMutation.isPending ? '⏳' : '➤'}
            </button>
          </div>
          <p className="text-xs text-slate-400 mt-1.5">
            Tekan Enter untuk kirim · Shift+Enter untuk baris baru · Maks 500 karakter
          </p>
        </div>
      </div>
    </>
  )
}
