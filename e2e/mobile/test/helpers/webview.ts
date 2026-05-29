export async function switchToWebView(timeout = 120_000): Promise<void> {
    const currentContext = await driver.getAppiumContext()
    if (typeof currentContext === 'string' && currentContext.startsWith('WEBVIEW')) {
        return
    }

    const elapsed = () => ((Date.now() - start) / 1000).toFixed(1)
    const start = Date.now()

    let webviewName: string | undefined
    while (Date.now() - start < timeout) {
        const contexts = await driver.getAppiumContexts()
        console.log(`[switchToWebView +${elapsed()}s] contexts: ${JSON.stringify(contexts)}`)
        webviewName = (contexts as string[]).find((c) => c.startsWith('WEBVIEW'))
        if (webviewName) break
        await driver.pause(2_000)
    }
    if (!webviewName) throw new Error(`No WEBVIEW context found within ${timeout}ms`)

    console.log(`[switchToWebView +${elapsed()}s] Switching to ${webviewName}`)
    await driver.switchAppiumContext(webviewName)
    console.log(`[switchToWebView +${elapsed()}s] Context switch done`)
}

export async function switchToNative(): Promise<void> {
    await driver.switchContext('NATIVE_APP')
}
