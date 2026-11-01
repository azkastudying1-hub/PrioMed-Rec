/*
 * web/src/uiux/primitives.tsx
 * ---------------------------------------------------------------------------
 * Komponen dasar (design primitives) yang dipakai seluruh layar baru.
 *
 * Semua komponen di sini sengaja "bodoh" (tanpa fetch / tanpa aturan klinis)
 * supaya mudah dipakai ulang dan mudah diuji. Aturan klinis ada di clinical.tsx,
 * sedangkan orkestrasi data ada di pages.tsx.
 *
 * Aksesibilitas yang sudah dibakukan:
 *  - Setiap tombol punya area sentuh minimal 40px dan focus ring jelas.
 *  - Modal menutup dengan Escape, mengunci scroll, dan memindahkan fokus.
 *  - Tabs mendukung ArrowLeft / ArrowRight.
 *  - Warna status selalu disertai teks, bukan hanya warna.
 */

import {
  forwardRef,
  useEffect,
  useId,
  useRef,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react"
import {
  AlertCircle,
  CheckCircle2,
  Info,
  LoaderCircle,
  TriangleAlert,
  X,
} from "lucide-react"

export type Tone =
  | "neutral"
  | "info"
  | "success"
  | "warning"
  | "danger"
  | "critical"
  | "teal"

export function cn(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ")
}

/** Membersihkan karakter mojibake dari data demo lama tanpa mengubah data asli. */
export function cleanText(value: string | null | undefined): string {
  if (value == null) return "—"
  const cleaned = value
    .replace(/\s*\uFFFD\+'?\s*/g, " → ")
    .replace(/\uFFFD\?o/g, "“")
    .replace(/\uFFFD\?\?/g, "”")
    .replace(/\uFFFD/g, "")
    .replace(/\s{2,}/g, " ")
    .trim()
  return cleaned || "—"
}

/* -------------------------------------------------------------------------- */
/* Badge                                                                      */
/* -------------------------------------------------------------------------- */

const badgeTones: Record<Tone, string> = {
  neutral: "border-slate-200 bg-slate-50 text-slate-700",
  info: "border-blue-200 bg-blue-50 text-blue-800",
  success: "border-emerald-200 bg-emerald-50 text-emerald-800",
  warning: "border-amber-200 bg-amber-50 text-amber-900",
  danger: "border-red-200 bg-red-50 text-red-800",
  critical: "border-red-300 bg-red-100 text-red-900",
  teal: "border-teal-200 bg-teal-50 text-teal-800",
}

const dotTones: Record<Tone, string> = {
  neutral: "bg-slate-400",
  info: "bg-blue-600",
  success: "bg-emerald-600",
  warning: "bg-amber-500",
  danger: "bg-red-600",
  critical: "bg-red-700",
  teal: "bg-teal-600",
}

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone
  icon?: ReactNode
  dot?: boolean
}

export function Badge({
  tone = "neutral",
  icon,
  dot = false,
  className,
  children,
  ...rest
}: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-semibold leading-none",
        badgeTones[tone],
        className,
      )}
      {...rest}
    >
      {dot && <span className={cn("size-1.5 rounded-full", dotTones[tone])} aria-hidden="true" />}
      {icon}
      {children}
    </span>
  )
}

/* -------------------------------------------------------------------------- */
/* Button                                                                     */
/* -------------------------------------------------------------------------- */

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "success" | "warning" | "subtle"
export type ButtonSize = "sm" | "md" | "lg" | "icon" | "icon-sm"

const buttonVariants: Record<ButtonVariant, string> = {
  primary:
    "border-transparent bg-blue-700 text-white shadow-sm hover:bg-blue-800 active:bg-blue-900",
  secondary:
    "border-slate-300 bg-white text-slate-800 shadow-sm hover:border-slate-400 hover:bg-slate-50",
  ghost:
    "border-transparent bg-transparent text-slate-700 hover:bg-slate-100 hover:text-slate-900",
  danger:
    "border-transparent bg-red-700 text-white shadow-sm hover:bg-red-800 active:bg-red-900",
  success:
    "border-transparent bg-emerald-700 text-white shadow-sm hover:bg-emerald-800 active:bg-emerald-900",
  warning:
    "border-transparent bg-amber-600 text-white shadow-sm hover:bg-amber-700 active:bg-amber-800",
  subtle:
    "border-slate-200 bg-slate-100 text-slate-700 hover:bg-slate-200",
}

const buttonSizes: Record<ButtonSize, string> = {
  sm: "min-h-9 px-3 text-xs",
  md: "min-h-10 px-4 text-sm",
  lg: "min-h-12 px-5 text-sm",
  icon: "size-10 p-0",
  "icon-sm": "size-8 p-0",
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  loading?: boolean
  icon?: ReactNode
  iconRight?: ReactNode
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "primary",
    size = "md",
    loading = false,
    icon,
    iconRight,
    className,
    children,
    disabled,
    type = "button",
    ...rest
  },
  ref,
) {
  return (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg border font-semibold transition",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-50",
        buttonVariants[variant],
        buttonSizes[size],
        className,
      )}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? (
        <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
      ) : (
        icon
      )}
      {children}
      {!loading && iconRight}
    </button>
  )
})

export interface IconButtonProps extends Omit<ButtonProps, "children" | "icon" | "size"> {
  label: string
  icon: ReactNode
  compact?: boolean
}

export function IconButton({ label, icon, variant = "ghost", compact = false, ...rest }: IconButtonProps) {
  return (
    <Button
      variant={variant}
      size={compact ? "icon-sm" : "icon"}
      aria-label={label}
      title={label}
      icon={icon}
      {...rest}
    />
  )
}

/* -------------------------------------------------------------------------- */
/* Card                                                                       */
/* -------------------------------------------------------------------------- */

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padded?: boolean
}

export function Card({ className, padded = true, children, ...rest }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-xl border border-slate-200 bg-white shadow-sm",
        padded && "p-5",
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Form controls                                                              */
/* -------------------------------------------------------------------------- */

const controlBase =
  "rounded-lg border bg-white text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:ring-2 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-500"

function controlState(invalid?: boolean) {
  return invalid
    ? "border-red-400 focus:border-red-600 focus:ring-red-100"
    : "border-slate-300 focus:border-blue-600 focus:ring-blue-100"
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { className, invalid, ...rest },
  ref,
) {
  return (
    <input
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(controlBase, controlState(invalid), "min-h-10 w-full px-3", className)}
      {...rest}
    />
  )
})

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { className, invalid, children, ...rest },
  ref,
) {
  return (
    <select
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(controlBase, controlState(invalid), "min-h-10 px-3 pr-8", className)}
      {...rest}
    >
      {children}
    </select>
  )
})

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { className, invalid, rows = 3, ...rest },
  ref,
) {
  return (
    <textarea
      ref={ref}
      rows={rows}
      aria-invalid={invalid || undefined}
      className={cn(controlBase, controlState(invalid), "min-h-20 w-full px-3 py-2", className)}
      {...rest}
    />
  )
})

export interface FieldProps {
  label: string
  htmlFor: string
  hint?: string
  error?: string
  required?: boolean
  children: ReactNode
  className?: string
}

export function Field({
  label,
  htmlFor,
  hint,
  error,
  required = false,
  children,
  className,
}: FieldProps) {
  return (
    <div className={cn("grid gap-1.5", className)}>
      <label htmlFor={htmlFor} className="text-xs font-semibold text-slate-700">
        {label}
        {required ? (
          <span className="ml-1 text-red-600" aria-hidden="true">
            *
          </span>
        ) : (
          <span className="ml-1 font-normal text-slate-400">(opsional)</span>
        )}
      </label>
      {children}
      {hint && !error && (
        <p id={`${htmlFor}-hint`} className="text-[11px] leading-relaxed text-slate-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${htmlFor}-error`} role="alert" className="text-[11px] font-medium text-red-700">
          {error}
        </p>
      )}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Tabs                                                                       */
/* -------------------------------------------------------------------------- */

export interface TabItem {
  id: string
  label: string
  icon?: ReactNode
  count?: number
}

export interface TabsProps {
  items: TabItem[]
  value: string
  onChange: (value: string) => void
  ariaLabel: string
  className?: string
}

export function Tabs({ items, value, onChange, ariaLabel, className }: TabsProps) {
  const refs = useRef<Array<HTMLButtonElement | null>>([])

  function moveFocus(index: number) {
    const next = items[index]
    if (!next) return
    onChange(next.id)
    refs.current[index]?.focus()
  }

  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={cn(
        "flex flex-wrap items-center gap-1 rounded-xl border border-slate-200 bg-white p-1 shadow-sm",
        className,
      )}
    >
      {items.map((item, index) => {
        const active = item.id === value
        return (
          <button
            key={item.id}
            ref={(node) => {
              refs.current[index] = node
            }}
            type="button"
            role="tab"
            id={`tab-${item.id}`}
            aria-selected={active}
            aria-controls={`panel-${item.id}`}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(item.id)}
            onKeyDown={(event) => {
              if (event.key === "ArrowRight") {
                event.preventDefault()
                moveFocus((index + 1) % items.length)
              }
              if (event.key === "ArrowLeft") {
                event.preventDefault()
                moveFocus((index - 1 + items.length) % items.length)
              }
            }}
            className={cn(
              "inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold transition",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600",
              active
                ? "bg-blue-700 text-white shadow-sm"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
            )}
          >
            {item.icon}
            {item.label}
            {typeof item.count === "number" && (
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 font-mono text-[10px]",
                  active ? "bg-white/15 text-white" : "bg-slate-100 text-slate-600",
                )}
              >
                {item.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Segmented control                                                          */
/* -------------------------------------------------------------------------- */

export interface SegmentOption<T extends string> {
  value: T
  label: string
  count?: number
}

export interface SegmentedControlProps<T extends string> {
  items: Array<SegmentOption<T>>
  value: T
  onChange: (value: T) => void
  ariaLabel: string
  className?: string
}

export function SegmentedControl<T extends string>({
  items,
  value,
  onChange,
  ariaLabel,
  className,
}: SegmentedControlProps<T>) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex flex-wrap items-center gap-1 rounded-xl border border-slate-200 bg-white p-1 shadow-sm",
        className,
      )}
    >
      {items.map((item) => {
        const active = item.value === value
        return (
          <button
            key={item.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(item.value)}
            className={cn(
              "inline-flex min-h-9 items-center gap-1.5 rounded-lg px-3 text-xs font-semibold transition",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600",
              active
                ? "bg-blue-700 text-white shadow-sm"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
            )}
          >
            {item.label}
            {typeof item.count === "number" && (
              <span
                className={cn(
                  "rounded px-1.5 py-0.5 font-mono text-[10px]",
                  active ? "bg-white/15 text-white" : "bg-slate-100 text-slate-600",
                )}
              >
                {item.count}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Modal                                                                      */
/* -------------------------------------------------------------------------- */

export interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  description?: string
  children: ReactNode
  footer?: ReactNode
  size?: "sm" | "md" | "lg"
}

const modalSizes = {
  sm: "max-w-md",
  md: "max-w-xl",
  lg: "max-w-3xl",
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
}: ModalProps) {
  const titleId = useId()
  const descriptionId = useId()
  const panelRef = useRef<HTMLDivElement>(null)
  const closeRef = useRef(onClose)

  useEffect(() => {
    closeRef.current = onClose
  }, [onClose])

  useEffect(() => {
    if (!open) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeRef.current()
    }
    const previousOverflow = document.body.style.overflow
    // Save the element that had focus before the modal opened so we can restore it on close.
    const previousActiveElement = document.activeElement as HTMLElement | null
    document.body.style.overflow = "hidden"
    document.addEventListener("keydown", onKeyDown)
    const focusTimer = window.setTimeout(() => panelRef.current?.focus(), 20)

    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener("keydown", onKeyDown)
      window.clearTimeout(focusTimer)
      // Restore focus to the triggering element when the modal closes.
      previousActiveElement?.focus()
    }
  }, [open])

  if (!open) return null

  return (
    <div
      className="pmr-enter fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose()
      }}
    >
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
        className={cn(
          "max-h-[90vh] w-full overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl outline-none",
          modalSizes[size],
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div>
            <h2 id={titleId} className="font-display text-base font-bold text-slate-900">
              {title}
            </h2>
            {description && (
              <p id={descriptionId} className="mt-1 text-xs leading-relaxed text-slate-500">
                {description}
              </p>
            )}
          </div>
          <IconButton label="Tutup dialog" icon={<X className="size-4" />} onClick={onClose} />
        </div>
        <div className="max-h-[calc(90vh-9rem)] overflow-y-auto px-5 py-4">{children}</div>
        {footer && (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-slate-200 bg-slate-50 px-5 py-3">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

/* -------------------------------------------------------------------------- */
/* Feedback states                                                            */
/* -------------------------------------------------------------------------- */

const alertTones: Record<Tone, string> = {
  neutral: "border-slate-200 bg-slate-50 text-slate-800",
  info: "border-blue-200 bg-blue-50 text-blue-950",
  success: "border-emerald-200 bg-emerald-50 text-emerald-950",
  warning: "border-amber-200 bg-amber-50 text-amber-950",
  danger: "border-red-200 bg-red-50 text-red-950",
  critical: "border-red-300 bg-red-100 text-red-950",
  teal: "border-teal-200 bg-teal-50 text-teal-950",
}

const alertIcons: Record<Tone, ReactNode> = {
  neutral: <Info className="size-4" />,
  info: <Info className="size-4" />,
  success: <CheckCircle2 className="size-4" />,
  warning: <TriangleAlert className="size-4" />,
  danger: <AlertCircle className="size-4" />,
  critical: <AlertCircle className="size-4" />,
  teal: <Info className="size-4" />,
}

export interface InlineAlertProps {
  tone?: Tone
  title: string
  children?: ReactNode
  icon?: ReactNode
  className?: string
  action?: ReactNode
}

export function InlineAlert({
  tone = "info",
  title,
  children,
  icon,
  className,
  action,
}: InlineAlertProps) {
  return (
    <div
      role={tone === "danger" || tone === "critical" ? "alert" : "status"}
      className={cn("flex items-start gap-3 rounded-xl border p-3.5", alertTones[tone], className)}
    >
      <span className="mt-0.5 shrink-0" aria-hidden="true">
        {icon ?? alertIcons[tone]}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-bold">{title}</p>
        {children && <div className="mt-1 text-xs leading-relaxed opacity-90">{children}</div>}
      </div>
      {action}
    </div>
  )
}

export interface EmptyStateProps {
  title: string
  description: string
  icon?: ReactNode
  action?: ReactNode
  className?: string
}

export function EmptyState({ title, description, icon, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center",
        className,
      )}
    >
      <div className="mb-3 flex size-12 items-center justify-center rounded-full bg-slate-100 text-slate-500">
        {icon ?? <Info className="size-5" />}
      </div>
      <h3 className="font-display text-sm font-bold text-slate-900">{title}</h3>
      <p className="mt-1 max-w-md text-xs leading-relaxed text-slate-500">{description}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export interface ErrorStateProps {
  title?: string
  description: string
  onRetry?: () => void
  retrying?: boolean
}

export function ErrorState({
  title = "Data belum dapat dimuat",
  description,
  onRetry,
  retrying = false,
}: ErrorStateProps) {
  return (
    <InlineAlert
      tone="danger"
      title={title}
      action={
        onRetry ? (
          <Button size="sm" variant="secondary" onClick={onRetry} loading={retrying}>
            Coba lagi
          </Button>
        ) : undefined
      }
    >
      {description}
    </InlineAlert>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-slate-200/80", className)}
      aria-hidden="true"
    />
  )
}

/* -------------------------------------------------------------------------- */
/* Small utilities                                                            */
/* -------------------------------------------------------------------------- */

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="rounded border border-slate-300 bg-slate-50 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-slate-600 shadow-sm">
      {children}
    </kbd>
  )
}

export function VisuallyHidden({ children }: { children: ReactNode }) {
  return <span className="sr-only">{children}</span>
}

export function SkipLink() {
  return (
    <a
      href="#pmr-main"
      className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded-lg focus:bg-white focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-blue-700 focus:shadow-lg"
    >
      Lewati ke konten utama
    </a>
  )
}
