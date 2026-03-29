import { registerPlugin } from "@capacitor/core"
import { TlsHttp } from "./tlsHttp"

const NativeCookies = registerPlugin("NativeCookies")
const FileTransfer = registerPlugin("FileTransfer")

interface BackupProcessorPlugin {
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

const BackupProcessor = registerPlugin<BackupProcessorPlugin>("BackupProcessor")
const ImageProcessor = registerPlugin<ImageProcessorPlugin>("ImageProcessor")

declare global {
  interface Window {
    NativeCookies: typeof NativeCookies
    FileTransfer: typeof FileTransfer
    BackupProcessor: typeof BackupProcessor
    ImageProcessor: typeof ImageProcessor
    TlsHttp: typeof TlsHttp
  }
}

window.NativeCookies = NativeCookies
window.FileTransfer = FileTransfer
window.BackupProcessor = BackupProcessor
window.ImageProcessor = ImageProcessor
window.TlsHttp = TlsHttp

export { NativeCookies, FileTransfer, BackupProcessor, ImageProcessor, TlsHttp }
