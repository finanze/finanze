export async function switchToWebView(timeout = 60_000): Promise<void> {
    const currentContext = await driver.getAppiumContext()
    if (typeof currentContext === 'string' && currentContext.startsWith('WEBVIEW')) {
        return
    }

    const start = Date.now()
    while (Date.now() - start < timeout) {
        const contexts = await driver.getAppiumContexts()
        console.log(`[switchToWebView +${((Date.now() - start) / 1000).toFixed(1)}s] contexts: ${JSON.stringify(contexts)}`)
        const webview = (contexts as string[]).find((c) =>
            c.startsWith('WEBVIEW'),
        )
        if (webview) {
            console.log(`[switchToWebView] switching to ${webview}`)
            await driver.switchAppiumContext(webview)
            return
        }
        await driver.pause(2_000)
    }
    throw new Error(`No WEBVIEW context found within ${timeout}ms`)
}

export async function switchToNative(): Promise<void> {
    await driver.switchContext('NATIVE_APP')
}
