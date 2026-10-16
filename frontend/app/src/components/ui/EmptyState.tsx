import type { ReactNode } from "react"
import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 px-6 py-10 text-center",
        className,
      )}
    >
      <div className="relative flex h-12 w-12 items-center justify-center">
        <div className="absolute inset-0 rounded-2xl bg-muted/70 rotate-6" />
        <div className="relative flex h-12 w-12 items-center justify-center rounded-2xl border border-border bg-background shadow-sm">
          <Icon className="h-5 w-5 text-muted-foreground" />
        </div>
      </div>
      <div className="max-w-xs space-y-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      {action}
    </div>
  )
}
