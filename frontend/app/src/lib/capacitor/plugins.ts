import { registerPlugin } from "@capacitor/core"
import { TlsHttp } from "./tlsHttp"

const NativeCookies = registerPlugin("NativeCookies")
const FileTransfer = registerPlugin("FileTransfer")

interface BackupProcessorPlugin {
  deleteFile(options: { fileName: string }): Promise<{ success: boolean }>
  getFilePath(options: {
    fileName: string
  }): Promise<{ path: string; exists: boolean }>
}

interface ImageProcessorPlugin {
  processImage(options: {
    data: string
    filename: string
    contentType: string
  }): Promise<{
    data: string
    filename: string
    contentType: string
    size: number
  }>
}

interface DeviceCountryPlugin {
  getCountryCodes(): Promise<{
    network?: string | null
    sim?: string | null
    locale?: string | null
    region?: string | null
  }>
}

const BackupProcessor = registerPlugin<BackupProcessorPlugin>("BackupProcessor")
const ImageProcessor = registerPlugin<ImageProcessorPlugin>("ImageProcessor")
const DeviceCountry = registerPlugin<DeviceCountryPlugin>("DeviceCountry")

declare global {
  interface Window {
    NativeCookies: typeof NativeCookies
    FileTransfer: typeof FileTransfer
    BackupProcessor: typeof BackupProcessor
    ImageProcessor: typeof ImageProcessor
    DeviceCountry: typeof DeviceCountry
    TlsHttp: typeof TlsHttp
  }
}

window.NativeCookies = NativeCookies
window.FileTransfer = FileTransfer
window.BackupProcessor = BackupProcessor
window.ImageProcessor = ImageProcessor
window.DeviceCountry = DeviceCountry
window.TlsHttp = TlsHttp

export {
  NativeCookies,
  FileTransfer,
  BackupProcessor,
  ImageProcessor,
  DeviceCountry,
  TlsHttp,
}
