import type { HTMLAttributes } from "react"
import { Sparkles } from "lucide-react"
import { cn } from "@/lib/utils"

export function ExternalSuggestionsSurface({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-lg border border-violet-500/30 bg-gradient-to-br from-violet-500/10 via-card to-sky-500/10 text-card-foreground",
        className,
      )}
      {...props}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute -right-16 -top-20 h-48 w-48 rounded-full bg-fuchsia-500/20 blur-3xl"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-24 -left-16 h-48 w-48 rounded-full bg-sky-500/20 blur-3xl"
      />
      <div className="relative">{children}</div>
    </div>
  )
}

export function ExternalSuggestionsIcon({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 via-fuchsia-500 to-amber-400 text-white shadow-md shadow-fuchsia-500/25",
        className,
      )}
    >
      <Sparkles className="h-5 w-5" />
    </span>
  )
}
