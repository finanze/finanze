import type { ReactNode } from "react"

const PlusBadge = () => (
  <span className="inline-flex items-center align-baseline">
    <span className="inline-flex items-center gap-0.5 rounded-md bg-gradient-to-r from-amber-500 to-orange-500 px-1.5 py-0.5 text-xs font-bold text-white leading-none">
      <span className="text-[0.6rem]">+</span>
      Plus
    </span>
  </span>
)

export function formatPlusMessage(template: string): ReactNode {
  const parts = template.split("{plus}")
  if (parts.length === 1) return template
  return (
    <>
      {parts[0]}
      <PlusBadge />
      {parts.slice(1).join("")}
    </>
  )
}
