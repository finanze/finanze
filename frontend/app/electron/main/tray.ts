import { app, Menu, Tray } from "electron"
import { join } from "node:path"

interface TrayConfig {
  publicPath: string
  onShowWindow: () => Promise<void>
  onAbout: () => void
}

let tray: Tray | null = null

export function createTray(config: TrayConfig): Tray {
  tray = new Tray(join(config.publicPath, "tray.png"))

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
