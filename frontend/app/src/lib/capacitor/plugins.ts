import { registerPlugin } from "@capacitor/core"

const NativeCookies = registerPlugin("NativeCookies")
const FileTransfer = registerPlugin("FileTransfer")

interface BackupProcessorPlugin {
  getFilePath(options: {
    fileName: string
  }): Promise<{ path: string; exists: boolean }>
}

const BackupProcessor = registerPlugin<BackupProcessorPlugin>("BackupProcessor")

declare global {
  interface Window {
    NativeCookies: typeof NativeCookies
    FileTransfer: typeof FileTransfer
    BackupProcessor: typeof BackupProcessor
  }
}

window.NativeCookies = NativeCookies
window.FileTransfer = FileTransfer
window.BackupProcessor = BackupProcessor

export { NativeCookies, FileTransfer, BackupProcessor }
