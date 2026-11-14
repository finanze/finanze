import { compressImageForUpload } from "@/lib/mobile"
import { isNativeMobile } from "@/lib/platform"

const AI_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"]
const MAX_AI_IMAGE_BYTES = 4 * 1024 * 1024
const EXIF_SCAN_BYTES = 128 * 1024
const JPEG_SOI = 0xffd8
const APP1 = 0xffe1
const EXIF_HEADER = 0x45786966
const LITTLE_ENDIAN = 0x4949
const ORIENTATION_TAG = 0x0112
const DEFAULT_ORIENTATION = 1

export const NATIVE_IMAGE_EXTENSIONS = [".heic", ".heif"]

export const isImageFile = (file: File) => {
  const name = file.name.toLowerCase()
  return (
    file.type.startsWith("image/") ||
    NATIVE_IMAGE_EXTENSIONS.some(extension => name.endsWith(extension))
  )
}

export async function jpegOrientation(file: Blob): Promise<number> {
  try {
    const view = new DataView(
      await file.slice(0, EXIF_SCAN_BYTES).arrayBuffer(),
    )
    if (view.getUint16(0) !== JPEG_SOI) return DEFAULT_ORIENTATION
    let offset = 2
    while (offset + 4 <= view.byteLength) {
      const marker = view.getUint16(offset)
      if ((marker & 0xff00) !== 0xff00) return DEFAULT_ORIENTATION
      if (marker === APP1 && view.getUint32(offset + 4) === EXIF_HEADER) {
        const tiff = offset + 10
        const little = view.getUint16(tiff) === LITTLE_ENDIAN
        const ifd = tiff + view.getUint32(tiff + 4, little)
        const entries = view.getUint16(ifd, little)
        for (let index = 0; index < entries; index++) {
          const entry = ifd + 2 + index * 12
          if (view.getUint16(entry, little) === ORIENTATION_TAG) {
            return view.getUint16(entry + 8, little)
          }
        }
        return DEFAULT_ORIENTATION
      }
      offset += 2 + view.getUint16(offset + 2)
    }
  } catch {
    return DEFAULT_ORIENTATION
  }
  return DEFAULT_ORIENTATION
}

export async function needsAIImageNormalization(file: File) {
  if (!AI_IMAGE_TYPES.includes(file.type)) return true
  if (file.size > MAX_AI_IMAGE_BYTES) return true
  return (
    file.type === "image/jpeg" &&
    (await jpegOrientation(file)) !== DEFAULT_ORIENTATION
  )
}

export async function prepareAIImageUpload(file: File): Promise<File> {
  if (!isNativeMobile() || !isImageFile(file)) return file
  if (!(await needsAIImageNormalization(file))) return file
  return compressImageForUpload(file)
}
