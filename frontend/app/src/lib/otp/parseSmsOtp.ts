export function parseSmsOtp(
  message: string,
  pinLength: number,
  pattern?: string | null,
): string | null {
  if (!message || pinLength <= 0) return null

  if (pattern) {
    try {
      const match = new RegExp(pattern).exec(message)
      if (!match || match[1] == null) return null
      const captured = match[1]
      if (!new RegExp(`^\\d{${pinLength}}$`).test(captured)) return null
      return captured
    } catch {
      return null
    }
  }

  const matches = message.match(new RegExp(`\\b\\d{${pinLength}}\\b`, "g"))
  if (!matches || matches.length === 0) return null
  if (matches.length === 1) return matches[0]

  const labeled = message.match(
    new RegExp(
      `(?:cod(?:e|igo|ice)|otp|pin|clave|passcode)[^0-9]{0,20}(\\d{${pinLength}})\\b`,
      "i",
    ),
  )
  return labeled?.[1] ?? null
}
