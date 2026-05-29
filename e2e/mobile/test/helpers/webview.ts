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

    if (driver.isAndroid) {
        console.log(`[switchToWebView +${elapsed()}s] Waiting for app to render in native context...`)
        try {
            await $('//android.widget.EditText')
                .waitForDisplayed({ timeout: Math.max(timeout - (Date.now() - start), 10_000) })
            console.log(`[switchToWebView +${elapsed()}s] App rendered, waiting for idle...`)
            await driver.pause(5_000)
        } catch {
            console.log(`[switchToWebView +${elapsed()}s] Native wait timed out, attempting switch anyway`)
        }
    }

    console.log(`[switchToWebView +${elapsed()}s] Switching to ${webviewName}`)
    const maxAttempts = driver.isAndroid ? 3 : 1
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
            console.log(`[switchToWebView +${elapsed()}s] Context switch attempt ${attempt}/${maxAttempts}`)
            await driver.switchAppiumContext(webviewName!)
            console.log(`[switchToWebView +${elapsed()}s] Context switch done`)
            return
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e)
            console.log(`[switchToWebView +${elapsed()}s] Attempt ${attempt} failed: ${msg}`)
            if (attempt === maxAttempts) throw e
            await driver.pause(3_000)
        }
    }
}

export async function switchToNative(): Promise<void> {
    await driver.switchContext('NATIVE_APP')
}
