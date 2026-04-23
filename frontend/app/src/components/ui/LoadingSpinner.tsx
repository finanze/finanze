import { cn } from "@/lib/utils"

interface LoadingSpinnerProps {
  size?: "sm" | "md" | "lg"
  className?: string
  color?: "default" | "invert"
}

export function LoadingSpinner({
  size = "md",
  color = "default",
  className,
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: "h-4 w-4 border-[1.5px]",
    md: "h-8 w-8 border-2",
    lg: "h-12 w-12 border-4",
  }

  const colorClasses = {
    default: "border-current border-t-transparent text-foreground",
    invert: "border-current border-t-transparent text-background",
  }

  return (
    <div
      className={cn(
        "animate-spin rounded-full",
        sizeClasses[size],
        colorClasses[color],
        className,
      )}
    />
  )
}
