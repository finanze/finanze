import { app, Menu, nativeImage, Tray } from "electron"
import { join } from "node:path"

interface TrayConfig {
  publicPath: string
  onShowWindow: () => Promise<void>
  onAbout: () => void
}

let tray: Tray | null = null

export function createTray(config: TrayConfig): Tray {
  const isMac = process.platform === "darwin"
  const defaultIconPath = join(config.publicPath, "tray.png")
  const macTemplateIconPath = join(config.publicPath, "trayTemplate.png")

  const resolvedIconPath = isMac ? macTemplateIconPath : defaultIconPath
  let trayImage = nativeImage.createFromPath(resolvedIconPath)

  if (trayImage.isEmpty() && isMac) {
    trayImage = nativeImage.createFromPath(defaultIconPath)
  }

  if (isMac) {
    trayImage.setTemplateImage(true)
  }

  tray = new Tray(trayImage.isEmpty() ? defaultIconPath : trayImage)

  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Finanze",
      click: async () => {
        await config.onShowWindow()
      },
    },
    { type: "separator" },
    {
      label: "About",
      click: () => {
        config.onAbout()
      },
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => {
        app.quit()
      },
    },
  ])

  tray.setToolTip("Finanze")
  tray.setContextMenu(contextMenu)

  tray.on("click", async () => {
    await config.onShowWindow()
  })

  return tray
}

export function getTray(): Tray | null {
  return tray
}
