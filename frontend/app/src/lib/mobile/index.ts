import { isNativeMobile } from "@/lib/platform"

export async function preinit(): Promise<void> {
  if (!__MOBILE__) return

  const { initializeCapacitorPlatform, applyNativeSafeAreaCssVars } =
    await import("@/lib/capacitor")
  await initializeCapacitorPlatform()
  await applyNativeSafeAreaCssVars()
}

export function init() {
  if (!__MOBILE__) return
  if (!isNativeMobile()) return

  // Set up mobile external login API
  import("@/lib/capacitor/loginHandlers").then(
    ({ promptLogin, onCompletedExternalLogin }) => {
      import("@/lib/externalLogin").then(({ setMobileLoginAPI }) => {
        setMobileLoginAPI({
          requestExternalLogin: (id, req) => promptLogin(id, req || {}),
          onCompletedExternalLogin,
        })
      })
    },
  )

  import("@/lib/pyodide/init").then(({ ensureCoreInitialized }) => {
    ensureCoreInitialized()
  })
}

export function triggerDeferredInit() {
  if (!__MOBILE__) return
  if (!isNativeMobile()) return

  import("@/lib/pyodide/init").then(({ triggerDeferredInit }) => {
    triggerDeferredInit()
  })
}

export function hideSplashScreen() {
  if (!__MOBILE__) return
  if (!isNativeMobile()) return

  import("@/lib/capacitor/init").then(({ hideSplashScreen }) => {
    hideSplashScreen()
  })
}

async function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onloadend = () => {
      if (reader.error) {
        reject(reader.error)
        return
      }
      const result = reader.result as string
      const commaIndex = result.indexOf(",")
      resolve(commaIndex >= 0 ? result.slice(commaIndex + 1) : result)
    }
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}

export async function compressImageForUpload(file: File): Promise<File> {
  if (!__MOBILE__) return file
  if (!isNativeMobile()) return file

  try {
    const { ImageProcessor } = await import("@/lib/capacitor/plugins")
    const buffer = await file.arrayBuffer()
    const bytes = new Uint8Array(buffer)
    let binary = ""
    for (let i = 0; i < bytes.length; i++) {
      binary += String.fromCharCode(bytes[i])
    }
    const base64Data = btoa(binary)
    const result = await ImageProcessor.processImage({
      data: base64Data,
      filename: file.name,
      contentType: file.type || "image/jpeg",
    })
    const binaryStr = atob(result.data)
    const resultBytes = new Uint8Array(binaryStr.length)
    for (let i = 0; i < binaryStr.length; i++) {
      resultBytes[i] = binaryStr.charCodeAt(i)
    }
    return new File([resultBytes], result.filename, {
      type: result.contentType,
    })
  } catch {
    return file
  }
}

function isTextFile(
  contentType: string | null | undefined,
  filename: string,
): boolean {
  if (contentType) {
    if (
      contentType.startsWith("text/") ||
      contentType === "application/json" ||
      contentType.includes("csv")
    ) {
      return true
    }
  }
  const ext = filename.split(".").pop()?.toLowerCase()
  return ["csv", "json", "txt", "xml", "html", "md"].includes(ext || "")
}

export async function saveBlobToDevice(params: {
  blob: Blob
  filename: string
  contentType?: string | null
}): Promise<boolean> {
  if (!__MOBILE__) return false
  if (!isNativeMobile()) return false

  try {
    const { Filesystem, Directory, Encoding } =
      await import("@capacitor/filesystem")
    const { Share } = await import("@capacitor/share")

    const safeName = params.filename?.trim() || "export"
    const path = `finanze/${safeName}`

    const mimeType = params.contentType || params.blob.type
    if (isTextFile(mimeType, safeName)) {
      const text = await params.blob.text()
      await Filesystem.writeFile({
        path,
        data: text,
        directory: Directory.Documents,
        encoding: Encoding.UTF8,
        recursive: true,
      })
    } else {
      const base64Data = await blobToBase64(params.blob)
      await Filesystem.writeFile({
        path,
        data: base64Data,
        directory: Directory.Documents,
        recursive: true,
      })
    }

    const uri = await Filesystem.getUri({
      path,
      directory: Directory.Documents,
    })

    await Share.share({
      title: safeName,
      url: uri.uri,
    })

    return true
  } catch {
    return false
  }
}
