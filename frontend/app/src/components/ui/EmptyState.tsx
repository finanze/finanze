import type { ReactNode } from "react"
import type { LucideIcon } from "lucide-react"
import { cn } from "@/lib/utils"

type EmptyStateProps = {
  title: string
  description?: string
  action?: ReactNode
  className?: string
  iconClassName?: string
} & (
  { icon: LucideIcon; iconNode?: never } | { icon?: never; iconNode: ReactNode }
)

export function EmptyState(props: EmptyStateProps) {
  const { title, description, action, className, iconClassName } = props
  const Icon = "icon" in props ? props.icon : undefined
  const iconNode = "iconNode" in props ? props.iconNode : undefined

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
          {iconNode ??
            (Icon ? (
              <Icon
                className={cn("h-5 w-5 text-muted-foreground", iconClassName)}
              />
            ) : null)}
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
