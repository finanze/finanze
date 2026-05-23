const SAMPLE_SIZE = 32

export function isMostlyWhiteLogo(image: HTMLImageElement): boolean {
  const canvas = document.createElement("canvas")
  canvas.width = SAMPLE_SIZE
  canvas.height = SAMPLE_SIZE

  const context = canvas.getContext("2d", { willReadFrequently: true })
  if (!context) return false

  context.clearRect(0, 0, SAMPLE_SIZE, SAMPLE_SIZE)
  context.drawImage(image, 0, 0, SAMPLE_SIZE, SAMPLE_SIZE)

  const { data } = context.getImageData(0, 0, SAMPLE_SIZE, SAMPLE_SIZE)
  let opaquePixels = 0
  let whitePixels = 0

  for (let index = 0; index < data.length; index += 4) {
    const alpha = data[index + 3]
    if (alpha < 32) continue

    opaquePixels += 1

    const red = data[index]
    const green = data[index + 1]
    const blue = data[index + 2]
    const minChannel = Math.min(red, green, blue)
    const maxChannel = Math.max(red, green, blue)

    if (minChannel >= 235 && maxChannel - minChannel <= 15) {
      whitePixels += 1
    }
  }

  if (opaquePixels === 0) return false

  return whitePixels / opaquePixels >= 0.9
}

export function isMostlyBlackLogo(image: HTMLImageElement): boolean {
  const canvas = document.createElement("canvas")
  canvas.width = SAMPLE_SIZE
  canvas.height = SAMPLE_SIZE

  const context = canvas.getContext("2d", { willReadFrequently: true })
  if (!context) return false

  context.clearRect(0, 0, SAMPLE_SIZE, SAMPLE_SIZE)
  context.drawImage(image, 0, 0, SAMPLE_SIZE, SAMPLE_SIZE)

  const { data } = context.getImageData(0, 0, SAMPLE_SIZE, SAMPLE_SIZE)
  let opaquePixels = 0
  let blackPixels = 0

  for (let index = 0; index < data.length; index += 4) {
    const alpha = data[index + 3]
    if (alpha < 32) continue

    opaquePixels += 1

    const red = data[index]
    const green = data[index + 1]
    const blue = data[index + 2]
    const maxChannel = Math.max(red, green, blue)

    if (maxChannel <= 20) {
      blackPixels += 1
    }
  }

  if (opaquePixels === 0) return false

  return blackPixels / opaquePixels >= 0.9
}

export function shouldInvertIcon(
  image: HTMLImageElement,
  isDarkMode: boolean,
): boolean {
  try {
    return isDarkMode ? isMostlyBlackLogo(image) : isMostlyWhiteLogo(image)
  } catch {
    return false
  }
}
