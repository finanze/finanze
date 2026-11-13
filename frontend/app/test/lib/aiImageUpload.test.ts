import { beforeEach, describe, expect, it, vi } from "vitest"

const { compressImageForUpload, nativeMobile } = vi.hoisted(() => ({
  compressImageForUpload: vi.fn(),
  nativeMobile: { value: true },
}))

vi.mock("@/lib/mobile", () => ({ compressImageForUpload }))
vi.mock("@/lib/platform", () => ({ isNativeMobile: () => nativeMobile.value }))

import {
  jpegOrientation,
  needsAIImageNormalization,
  prepareAIImageUpload,
} from "@/lib/aiImageUpload"

function exifJpeg(orientation: number) {
  const bytes = [
    0xff,
    0xd8,
    0xff,
    0xe1,
    0x00,
    0x22,
    0x45,
    0x78,
    0x69,
    0x66,
    0x00,
    0x00,
    0x4d,
    0x4d,
    0x00,
    0x2a,
    0x00,
    0x00,
    0x00,
    0x08,
    0x00,
    0x01,
    0x01,
    0x12,
    0x00,
    0x03,
    0x00,
    0x00,
    0x00,
    0x01,
    0x00,
    orientation,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0x00,
    0xff,
    0xd9,
  ]
  return new File([new Uint8Array(bytes)], "photo.jpg", { type: "image/jpeg" })
}

beforeEach(() => {
  vi.clearAllMocks()
  nativeMobile.value = true
  compressImageForUpload.mockImplementation(
    async (file: File) =>
      new File([file], "converted.jpg", { type: "image/jpeg" }),
  )
})

describe("AI image uploads", () => {
  it("reads the EXIF orientation of JPEG files", async () => {
    expect(await jpegOrientation(exifJpeg(6))).toBe(6)
    expect(await jpegOrientation(exifJpeg(1))).toBe(1)
    expect(await jpegOrientation(new Blob(["not an image"]))).toBe(1)
  })

  it("normalizes only unsupported, rotated or oversized images", async () => {
    const png = new File(["png"], "receipt.png", { type: "image/png" })
    const heic = new File(["heic"], "receipt.heic", { type: "image/heic" })
    const large = new File([new Uint8Array(4 * 1024 * 1024 + 1)], "big.png", {
      type: "image/png",
    })

    expect(await needsAIImageNormalization(png)).toBe(false)
    expect(await needsAIImageNormalization(exifJpeg(1))).toBe(false)
    expect(await needsAIImageNormalization(exifJpeg(6))).toBe(true)
    expect(await needsAIImageNormalization(heic)).toBe(true)
    expect(await needsAIImageNormalization(large)).toBe(true)
  })

  it("converts images with the native processor only on mobile", async () => {
    const heic = new File(["heic"], "receipt.heic", { type: "" })
    const png = new File(["png"], "receipt.png", { type: "image/png" })

    expect((await prepareAIImageUpload(heic)).name).toBe("converted.jpg")
    expect(await prepareAIImageUpload(png)).toBe(png)

    nativeMobile.value = false
    expect(await prepareAIImageUpload(heic)).toBe(heic)
    expect(compressImageForUpload).toHaveBeenCalledTimes(1)
  })
})
