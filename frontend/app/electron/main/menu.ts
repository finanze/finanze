import {
    type BrowserWindow,
    Menu,
    type MenuItemConstructorOptions,
} from 'electron'

export function createMenu(mainWindow: BrowserWindow) {
    const template: MenuItemConstructorOptions[] = [
        {
            label: 'File',
            submenu: [{ role: 'quit' }],
        },
        {
            label: 'Edit',
            submenu: [{ role: 'cut' }, { role: 'copy' }, { role: 'paste' }],
        },
        {
            label: 'View',
            submenu: [
                { role: 'reload' },
                { role: 'forceReload' },
                { type: 'separator' },
                { role: 'resetZoom' },
                { role: 'zoomIn' },
                { role: 'zoomOut' },
                { type: 'separator' },
                { role: 'togglefullscreen' },
            ],
        },
        {
            label: 'Help',
            submenu: [
                {
                    label: 'About',
                    click: () => mainWindow?.webContents?.send('show-about'),
                },
            ],
        },
    ]

    const menu = Menu.buildFromTemplate(template)
    Menu.setApplicationMenu(menu)
}
