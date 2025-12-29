export async function copyToClipboard(text: string): Promise<boolean> {
  if (!text) {
    return false
  }

  try {
    if (typeof navigator !== "undefined" && navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // Fall back to execCommand below.
  }

  try {
    if (typeof document === "undefined") {
      return false
    }

    const textArea = document.createElement("textarea")
    textArea.value = text
    textArea.setAttribute("readonly", "")
    textArea.style.position = "absolute"
    textArea.style.left = "-9999px"

    document.body.appendChild(textArea)
    textArea.select()

    const ok = document.execCommand("copy")
    document.body.removeChild(textArea)

    return ok
  } catch {
    return false
  }
}
