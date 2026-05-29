export async function switchToWebView(timeout = 60_000): Promise<void> {
    const start = Date.now()
    let lastError: unknown
    while (Date.now() - start < timeout) {
        try {
            const remaining = timeout - (Date.now() - start)
            await driver.switchContext({
                url: /./,
                androidWebviewConnectTimeout: Math.min(10_000, remaining),
                androidWebviewConnectionRetryTime: 1_000,
            })
            return
        } catch (e) {
            lastError = e
            await driver.pause(2_000)
        }
    }
    throw lastError ?? new Error(`No WEBVIEW context found within ${timeout}ms`)
}

export async function switchToNative(): Promise<void> {
    await driver.switchContext('NATIVE_APP')
}
