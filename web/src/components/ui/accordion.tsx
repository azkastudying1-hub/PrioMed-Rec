import React, { useState } from "react"

export function Accordion({
  children,
}: {
  children: React.ReactNode
}) {
  return <div className="space-y-2">{children}</div>
}

export function AccordionItem({
  value,
  children,
}: {
  value: string
  children: React.ReactNode
}) {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="border rounded-lg">
      <button
        type="button"
        className="w-full text-left px-4 py-3 font-medium text-slate-700 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 flex items-center justify-between"
        onClick={() => setIsOpen(!isOpen)}
      >
        <span>Click to expand</span>
        <span className="text-xs text-slate-400">{isOpen ? "▲" : "▼"}</span>
      </button>
      {isOpen && (
        <div className="px-4 py-3 border-t border-slate-200 bg-slate-50">
          {children}
        </div>
      )}
    </div>
  )
}

export function AccordionItemTrigger({
  value,
  children,
}: {
  value: string
  children: React.ReactNode
}) {
  return <>{children}</>
}

export function AccordionItemContent({
  children,
}: {
  children: React.ReactNode
}) {
  return <>{children}</>
}