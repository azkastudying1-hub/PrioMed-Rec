import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react"
import { AlertCircle, LoaderCircle, RotateCcw, X } from "lucide-react"

export function Heading({
  level = 1,
  children,
  className = "",
}: {
  level?: 1 | 2 | 3 | 4
  children: ReactNode
  className?: string
}) {
  const sizes = {
    1: "text-2xl lg:text-[1.75rem]",
    2: "text-xl",
    3: "text-base",
    4: "text-sm",
  }
  return (
    <div
      role="heading"
      aria-level={level}
      className={`font-['Plus_Jakarta_Sans'] font-bold tracking-tight text-slate-950 ${sizes[level]} ${className}`}
    >
      {children}
    </div>
  )
}

export function Button({
  variant = "primary",
  size = "md",
  loading,
  icon,
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger" | "success"
  size?: "sm" | "md" | "lg"
  loading?: boolean
  icon?: ReactNode
}) {
  const variants = {
    primary: "bg-blue-600 text-white border-blue-600 hover:bg-blue-700",
    secondary: "bg-white text-slate-800 border-slate-300 hover:bg-slate-50",
    ghost:
      "bg-transparent text-slate-700 border-transparent hover:bg-slate-100",
    danger: "bg-red-700 text-white border-red-700 hover:bg-red-800",
    success:
      "bg-emerald-700 text-white border-emerald-700 hover:bg-emerald-800",
  }
  const sizes = {
    sm: "min-h-9 px-3 text-xs",
    md: "min-h-10 px-4 text-sm",
    lg: "min-h-12 px-5 text-base",
  }
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-md border font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading ? (
        <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
      ) : (
        icon
      )}
      {children}
    </button>
  )
}

export function IconButton({
  label,
  children,
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string
  children: ReactNode
}) {
  return (
    <button
      aria-label={label}
      title={label}
      className={`inline-flex size-10 items-center justify-center rounded-md text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

export function Field({
  label,
  hint,
  required,
  children,
  className = "",
}: {
  label: string
  hint?: string
  required?: boolean
  children: ReactNode
  className?: string
}) {
  return (
    <label
      className={`grid gap-1.5 text-sm font-semibold text-slate-700 ${className}`}
    >
      <span>
        {label}
        {!required && (
          <span className="ml-1 font-normal text-slate-400">(opsional)</span>
        )}
      </span>
      {children}
      {hint && (
        <span className="text-xs font-normal text-slate-500">{hint}</span>
      )}
    </label>
  )
}

const controlClass =
  "min-h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900 outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100"

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input className={`${controlClass} ${props.className ?? ""}`} {...props} />
  )
}

export function Checkbox({ label }: { label: string }) {
  return (
    <label className="flex items-start gap-3 rounded-md border border-slate-200 p-3 text-sm">
      <input type="checkbox" className="mt-0.5 size-4 accent-blue-600" />
      <span>{label}</span>
    </label>
  )
}

export function Select({
  options,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & {
  options: Array<{ value: string; label: string }>
}) {
  return (
    <select className={`${controlClass} ${props.className ?? ""}`} {...props}>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  )
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={`${controlClass} min-h-28 resize-y py-2.5 ${props.className ?? ""}`}
      {...props}
    />
  )
}

export function Card({
  children,
  variant = "default",
  className = "",
  id,
}: {
  children: ReactNode
  variant?: "default" | "compact" | "emphasized" | "warning"
  className?: string
  id?: string
}) {
  const variants = {
    default: "border-slate-200 bg-white p-5",
    compact: "border-slate-200 bg-white p-4",
    emphasized: "border-blue-200 bg-blue-50/40 p-5",
    warning: "border-amber-300 bg-amber-50 p-4",
  }
  return (
    <div
      id={id}
      className={`rounded-lg border shadow-[0_1px_2px_rgba(15,23,42,0.04)] ${variants[variant]} ${className}`}
    >
      {children}
    </div>
  )
}

export function Badge({
  children,
  tone = "neutral",
  className = "",
}: {
  children: ReactNode
  tone?: "neutral" | "info" | "warning" | "success" | "danger" | "cyan"
  className?: string
}) {
  const tones = {
    neutral: "border-slate-300 bg-slate-100 text-slate-700",
    info: "border-blue-300 bg-blue-50 text-blue-800",
    warning: "border-amber-300 bg-amber-50 text-amber-800",
    success: "border-emerald-300 bg-emerald-50 text-emerald-800",
    danger: "border-red-300 bg-red-50 text-red-800",
    cyan: "border-cyan-300 bg-cyan-50 text-cyan-900",
  }
  return (
    <span
      className={`inline-flex min-h-6 items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[0.6875rem] font-bold leading-4 ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  )
}

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded bg-slate-200 ${className}`}
    />
  )
}

export function PageSkeleton({
  type = "table",
}: {
  type?: "table" | "detail" | "form"
}) {
  return (
    <div className="space-y-5" aria-label="Memuat konten">
      <Skeleton className="h-8 w-64" />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[1, 2, 3, 4].map((item) => (
          <Skeleton key={item} className="h-24" />
        ))}
      </div>
      <Skeleton className={type === "table" ? "h-96" : "h-[32rem]"} />
    </div>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <Card className="flex min-h-72 flex-col items-center justify-center text-center">
      <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        <AlertCircle className="size-6" aria-hidden="true" />
      </div>
      <Heading level={2}>{title}</Heading>
      <p className="mt-2 max-w-lg text-sm text-slate-600">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </Card>
  )
}

export function ErrorState({
  retry,
  title = "Data tidak dapat dimuat",
}: {
  retry: () => void
  title?: string
}) {
  return (
    <Card className="flex min-h-72 flex-col items-center justify-center border-red-200 text-center">
      <div className="mb-4 flex size-12 items-center justify-center rounded-full bg-red-50 text-red-700">
        <AlertCircle className="size-6" aria-hidden="true" />
      </div>
      <Heading level={2}>{title}</Heading>
      <p className="mt-2 max-w-lg text-sm text-slate-600">
        Koneksi demo gagal. Data klinis belum diubah. Coba muat kembali halaman
        ini.
      </p>
      <Button
        className="mt-5"
        variant="secondary"
        icon={<RotateCcw className="size-4" />}
        onClick={retry}
      >
        Coba lagi
      </Button>
    </Card>
  )
}

export function Modal({
  open,
  title,
  children,
  onClose,
  footer,
}: {
  open: boolean
  title: string
  children: ReactNode
  onClose: () => void
  footer?: ReactNode
}) {
  if (!open) return null
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className="max-h-[90vh] w-full max-w-xl overflow-auto rounded-xl border border-slate-200 bg-white shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <Heading level={2}>{title}</Heading>
          <IconButton label="Tutup dialog" onClick={onClose}>
            <X className="size-5" />
          </IconButton>
        </div>
        <div className="p-5">{children}</div>
        {footer && (
          <div className="flex justify-end gap-3 border-t border-slate-200 bg-slate-50 px-5 py-4">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}
