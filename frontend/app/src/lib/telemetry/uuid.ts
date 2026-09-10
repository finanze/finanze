// crypto.randomUUID is secure-context only, so it is missing when the web build
// is served over plain HTTP. getRandomValues has no such restriction.
export function randomUuid(): string {
  const impl = globalThis.crypto as Crypto | undefined

  if (impl?.randomUUID) return impl.randomUUID()

  const bytes = new Uint8Array(16)
  if (impl?.getRandomValues) {
    impl.getRandomValues(bytes)
  } else {
    for (let i = 0; i < bytes.length; i++) {
      bytes[i] = Math.floor(Math.random() * 256)
    }
  }

  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80

  const hex = Array.from(bytes, b => b.toString(16).padStart(2, "0")).join("")
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20),
  ].join("-")
}
