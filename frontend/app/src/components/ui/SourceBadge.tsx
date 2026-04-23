import type { ReactNode } from "react"
import React from "react"
import type { LucideIcon } from "lucide-react"
import { FileSpreadsheet, UserRoundPen } from "lucide-react"
import { Badge } from "./Badge"
import { cn } from "@/lib/utils"
import { DataSource } from "@/types"

export const getSourceIcon = (source: DataSource): LucideIcon | null => {
  switch (source) {
    case DataSource.MANUAL:
      return UserRoundPen
    case DataSource.SHEETS:
      return FileSpreadsheet
    default:
      return null
  }
}

interface SourceBadgeProps {
  source: DataSource
  title?: string
  className?: string
  iconClassName?: string
  children?: ReactNode
  onClick?: () => void
}

export function SourceBadge({
  source,
  title,
  className,
  iconClassName,
  children,
  onClick,
}: SourceBadgeProps) {
  const Icon = getSourceIcon(source)
  if (!Icon) return null

  return (
    <Badge
      className={cn(
        "inline-flex min-h-[1.5rem] items-center justify-center gap-1 px-2 py-0.5 text-xs leading-none bg-muted text-muted-foreground/90 dark:bg-muted/80",
        onClick && "cursor-pointer hover:bg-muted/60 transition-colors",
        className,
      )}
      title={title}
      onClick={onClick}
      {...(onClick && {
        role: "button" as const,
        tabIndex: 0,
        onKeyDown: (e: React.KeyboardEvent) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault()
            onClick()
          }
        },
      })}
    >
      <Icon className={cn("h-3.5 w-3.5", iconClassName)} />
      {children}
    </Badge>
  )
}
