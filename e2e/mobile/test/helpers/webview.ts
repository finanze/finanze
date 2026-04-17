export async function switchToWebView(timeout = 30_000): Promise<void> {
    const start = Date.now()
    while (Date.now() - start < timeout) {
        const contexts = await driver.getContexts()
        const webview = (contexts as string[]).find((c) =>
            c.startsWith('WEBVIEW'),
        )
        if (webview) {
            await driver.switchContext(webview)
            return
        }
        await driver.pause(500)
    }
    throw new Error(`No WEBVIEW context found within ${timeout}ms`)
}

export async function switchToNative(): Promise<void> {
    await driver.switchContext('NATIVE_APP')
}
