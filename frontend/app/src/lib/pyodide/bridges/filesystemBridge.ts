import { Capacitor } from "@capacitor/core"
import { Filesystem, Directory, Encoding } from "@capacitor/filesystem"
import { ImageProcessor } from "@/lib/capacitor/plugins"

const UPLOADS_DIR = "finanze_uploads"

const IMAGE_EXTENSIONS = new Set([
  ".jpg",
  ".jpeg",
  ".png",
  ".webp",
  ".gif",
  ".tif",
  ".tiff",
  ".bmp",
])

function isNativeMobile(): boolean {
  const platform = Capacitor.getPlatform()
  return platform === "ios" || platform === "android"
}

function isImageFile(filename: string, contentType?: string): boolean {
  if (contentType?.toLowerCase().startsWith("image/")) {
    return true
  }
  const ext = filename.toLowerCase().slice(filename.lastIndexOf("."))
  return IMAGE_EXTENSIONS.has(ext)
}

async function processAndWriteImage(
  folder: string,
  data: string,
  filename: string,
  contentType: string,
): Promise<{ path: string; filename: string }> {
  if (!isNativeMobile()) {
    const path = `${folder}/${filename}`
    const fullPath = `${UPLOADS_DIR}/${path}`
    await Filesystem.writeFile({
      path: fullPath,
      data,
      directory: Directory.Documents,
      recursive: true,
    })
    return { path, filename }
  }

  const processed = await ImageProcessor.processImage({
    data,
    filename,
    contentType,
  })

  const path = `${folder}/${processed.filename}`
  const fullPath = `${UPLOADS_DIR}/${path}`
  await Filesystem.writeFile({
    path: fullPath,
    data: processed.data,
    directory: Directory.Documents,
    recursive: true,
  })

  return { path, filename: processed.filename }
}

async function writeFile(
  path: string,
  data: string,
  isBase64: boolean,
): Promise<void> {
  const fullPath = `${UPLOADS_DIR}/${path}`

  if (isBase64) {
    await Filesystem.writeFile({
      path: fullPath,
      data,
      directory: Directory.Documents,
      recursive: true,
    })
  } else {
    await Filesystem.writeFile({
      path: fullPath,
      data,
      directory: Directory.Documents,
      encoding: Encoding.UTF8,
      recursive: true,
    })
  }
}

async function readFile(path: string, asBase64: boolean): Promise<string> {
  const fullPath = `${UPLOADS_DIR}/${path}`

  if (asBase64) {
    const result = await Filesystem.readFile({
      path: fullPath,
      directory: Directory.Documents,
    })
    if (typeof result.data === "string") {
      return result.data
    }
    if (result.data instanceof Blob) {
      const buffer = await result.data.arrayBuffer()
      const bytes = new Uint8Array(buffer)
      let binary = ""
      for (let i = 0; i < bytes.length; i++) {
        binary += String.fromCharCode(bytes[i])
      }
      return btoa(binary)
    }
    return ""
  } else {
    const result = await Filesystem.readFile({
      path: fullPath,
      directory: Directory.Documents,
      encoding: Encoding.UTF8,
    })
    return result.data as string
  }
}

async function deleteFile(path: string): Promise<boolean> {
  try {
    const fullPath = `${UPLOADS_DIR}/${path}`
    await Filesystem.deleteFile({
      path: fullPath,
      directory: Directory.Documents,
    })
    return true
  } catch {
    return false
  }
}

async function fileExists(path: string): Promise<boolean> {
  try {
    const fullPath = `${UPLOADS_DIR}/${path}`
    await Filesystem.stat({
      path: fullPath,
      directory: Directory.Documents,
    })
    return true
  } catch {
    return false
  }
}

async function getFileUri(path: string): Promise<string> {
  const fullPath = `${UPLOADS_DIR}/${path}`

  if (!isNativeMobile()) {
    const result = await Filesystem.readFile({
      path: fullPath,
      directory: Directory.Documents,
    })
    const data = result.data as string
    return `data:application/octet-stream;base64,${data}`
  }

  const result = await Filesystem.getUri({
    path: fullPath,
    directory: Directory.Documents,
  })
  return Capacitor.convertFileSrc(result.uri)
}

async function createDirectory(path: string): Promise<void> {
  const fullPath = `${UPLOADS_DIR}/${path}`
  try {
    await Filesystem.mkdir({
      path: fullPath,
      directory: Directory.Documents,
      recursive: true,
    })
  } catch {
    // Directory may already exist
  }
}

export const filesystemBridge = {
  writeFile,
  readFile,
  deleteFile,
  fileExists,
  getFileUri,
  createDirectory,
  processAndWriteImage,
  isImageFile,
}
