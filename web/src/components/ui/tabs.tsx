import React, { useState, useCallback } from "react"

interface TabsContextType {
  value: string
  onChange: (value: string) => void
  setValue: (value: string) => void
}

const TabsContext = React.createContext<TabsContextType>({
  value: "",
  onChange: () => {},
  setValue: () => {},
})

export function Tabs({
  defaultValue = "first",
  onValueChange,
  children,
}: {
  defaultValue?: string
  onValueChange?: (value: string) => void
  children: React.ReactNode
}) {
  const [value, setValue] = useState(defaultValue)

  const handleChange = useCallback(
    (newValue: string) => {
      setValue(newValue)
      onValueChange?.(newValue)
    },
    [onValueChange],
  )

  return (
    <TabsContext.Provider value={{ value, onChange: handleChange, setValue }}>
      <div className="flex gap-2 border-b border-slate-200 pb-2">
        {children}
      </div>
    </TabsContext.Provider>
  )
}

export function Tab({
  value,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  value: string
  children: React.ReactNode
}) {
  const tabsContext = React.useContext(TabsContext)

  return (
    <button
      role="tab"
      aria-selected={tabsContext.value === value}
      onClick={() => tabsContext.onChange(value)}
      className={`inline-flex items-center rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 disabled:cursor-not-allowed disabled:opacity-50 ${
        tabsContext.value === value
          ? "bg-blue-600 text-white"
          : "bg-slate-100 text-slate-700 hover:bg-slate-200"
      }`}
      {...props}
    >
      {children}
    </button>
  )
}