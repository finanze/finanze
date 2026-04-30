export interface FloatingLogo {
  x: number
  y: number
  rotation: number
  size: number
  opacity: number
}

export function generateFloatingLogos(
  count = 80,
  maxAttempts = 600,
): FloatingLogo[] {
  const items: FloatingLogo[] = []
  let seed = 42
  const rand = () => {
    seed = (seed * 16807) % 2147483647
    return (seed - 1) / 2147483646
  }
  const tooClose = (x: number, y: number, size: number) => {
    const margin = 1.2
    return items.some(item => {
      const minDist = ((size + item.size) / 2) * margin
      const dx = Math.abs(x - item.x) * 3.6
      const dy = Math.abs(y - item.y) * 5.5
      return dx < minDist && dy < minDist
    })
  }
  let attempts = 0
  while (items.length < count && attempts < maxAttempts) {
    attempts++
    const size = 12 + rand() * 16
    const x = rand() * 94 + 3
    const y = rand() * 100
    if (tooClose(x, y, size)) continue
    items.push({
      x,
      y,
      rotation: rand() * 120 - 60,
      size,
      opacity: 0.06 + rand() * 0.1,
    })
  }
  return items
}
