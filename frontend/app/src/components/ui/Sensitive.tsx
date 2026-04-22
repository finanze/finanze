import { isValidElement, type ReactNode } from "react"
import { useDataDisplayMode } from "@/context/DataDisplayModeContext"
import { DataDisplayMode } from "@/types"

function extractText(node: ReactNode): string {
  if (node == null || typeof node === "boolean") return ""
  if (typeof node === "string") return node
  if (typeof node === "number") return String(node)
  if (Array.isArray(node)) return node.map(extractText).join("")
  if (isValidElement(node))
    return extractText((node.props as { children?: ReactNode }).children)
  return ""
}

function maskText(text: string): string {
  return text
    .replace(/[+\-\u2212]/g, "")
    .replace(/\d[\d.,]*/g, "••••")
    .trim()
}

export function Sensitive({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  const { mode } = useDataDisplayMode()
  if (mode === DataDisplayMode.PRIVATE) {
    const masked = maskText(extractText(children))
    return (
      <span
        className={`${className ?? "text-foreground"} select-none pointer-events-none`}
      >
        {masked}
      </span>
    )
  }
  return <>{children}</>
}
