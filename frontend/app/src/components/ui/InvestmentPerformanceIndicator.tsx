import { cn } from "@/lib/utils"
import { Sensitive } from "@/components/ui/Sensitive"

export function InvestmentPerformanceIndicator({
  value,
  locale,
  className,
}: {
  value: number
  locale: string
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-1 text-sm",
        value >= 0 ? "text-green-500" : "text-red-500",
        className,
      )}
    >
      <Sensitive>
        <span className="text-sm font-black leading-none" aria-hidden="true">
          {value >= 0 ? "▴" : "▾"}
        </span>
        <span>
          {Math.abs(value).toLocaleString(locale, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
          %
        </span>
      </Sensitive>
    </div>
  )
}
