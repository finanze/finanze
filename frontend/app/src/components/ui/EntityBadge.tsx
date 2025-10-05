import type { HTMLAttributes, ReactNode } from "react"
import { Badge, type BadgeProps } from "@/components/ui/Badge"
import { cn, getColorForName } from "@/lib/utils"
import { EntityOrigin } from "@/types"

export interface EntityBadgeProps
  extends Omit<BadgeProps, "variant" | "children">,
    Pick<HTMLAttributes<HTMLDivElement>, "onClick" | "title"> {
  name: string
  origin?: EntityOrigin | null
  children?: ReactNode
  showVirtualTag?: boolean
}

export function EntityBadge({
  name,
  origin,
  children,
  className,
  onClick,
  showVirtualTag = true,
  title,
  ...rest
}: EntityBadgeProps) {
  const isClickable = typeof onClick === "function"

  return (
    <Badge
      {...rest}
      variant="outline"
      title={title}
      className={cn(
        "gap-1 whitespace-normal break-words px-2.5 py-0.5 text-xs font-semibold",
        getColorForName(name),
        isClickable && "cursor-pointer transition-opacity hover:opacity-80",
        className,
      )}
      onClick={onClick}
    >
      <span>{children ?? name}</span>
      {showVirtualTag && origin === EntityOrigin.MANUAL && (
        <span className="text-[0.65rem] opacity-70">(V)</span>
      )}
    </Badge>
  )
}
