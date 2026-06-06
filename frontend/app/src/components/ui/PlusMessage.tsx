import type { ReactNode } from "react"
import type { FFValue } from "@/types"

const PLUS_JOIN_EMAIL = "joinplus@finanze.me"

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

function formatJoinMessage(
  template: string,
  subject: string,
  body: string,
): ReactNode {
  const href = `mailto:${PLUS_JOIN_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
  const emailLink = (key: number) => (
    <span
      key={key}
      role="link"
      tabIndex={0}
      className="underline font-medium cursor-pointer"
      onClick={() => window.open(href, "_blank")}
      onKeyDown={e => {
        if (e.key === "Enter") window.open(href, "_blank")
      }}
    >
      {PLUS_JOIN_EMAIL}
    </span>
  )
  const segments = template.split(/\{plus\}|\{email\}/)
  if (segments.length === 1) return template
  const tokens = [...template.matchAll(/\{plus\}|\{email\}/g)].map(m => m[0])
  const result: ReactNode[] = [segments[0]]
  for (let i = 0; i < tokens.length; i++) {
    result.push(tokens[i] === "{plus}" ? <PlusBadge key={i} /> : emailLink(i))
    result.push(segments[i + 1])
  }
  return <>{result}</>
}

export function formatPlusToast(
  template: string,
  plusFlag: FFValue | undefined,
  joinText?: string,
  joinSubject?: string,
  joinBody?: string,
): ReactNode | null {
  if (plusFlag === "OFF") return null
  const base = formatPlusMessage(template)
  if (plusFlag === "JOIN" && joinText && joinSubject && joinBody) {
    return (
      <>
        {base}
        <br />
        {formatJoinMessage(joinText, joinSubject, joinBody)}
      </>
    )
  }
  return base
}
