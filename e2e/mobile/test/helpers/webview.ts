export async function switchToWebView(timeout = 120_000): Promise<void> {
    const currentContext = await driver.getAppiumContext()
    if (
        typeof currentContext === 'string' &&
        currentContext.startsWith('WEBVIEW')
    ) {
        return
    }

    const elapsed = () => ((Date.now() - start) / 1000).toFixed(1)
    const start = Date.now()

    let webviewName: string | undefined
    while (Date.now() - start < timeout) {
        const contexts = await driver.getAppiumContexts()
        console.log(
            `[switchToWebView +${elapsed()}s] contexts: ${JSON.stringify(contexts)}`,
        )
        webviewName = pickAppWebview(contexts as string[])
        if (webviewName) break
        await driver.pause(2_000)
    }
    if (!webviewName)
        throw new Error(`No WEBVIEW context found within ${timeout}ms`)

    if (driver.isAndroid) {
        console.log(
            `[switchToWebView +${elapsed()}s] Waiting for app to render in native context...`,
        )
        try {
            await $('//android.widget.EditText').waitForDisplayed({
                timeout: 20_000,
            })
            console.log(
                `[switchToWebView +${elapsed()}s] App rendered, waiting for idle...`,
            )
            await driver.pause(2_000)
        } catch {
            console.log(
                `[switchToWebView +${elapsed()}s] Native wait timed out, attempting switch anyway`,
            )
        }
    }

    console.log(`[switchToWebView +${elapsed()}s] Switching to ${webviewName}`)
    const maxAttempts = driver.isAndroid ? 3 : 1
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
        try {
            console.log(
                `[switchToWebView +${elapsed()}s] Context switch attempt ${attempt}/${maxAttempts}`,
            )
            await driver.switchAppiumContext(webviewName!)
            console.log(`[switchToWebView +${elapsed()}s] Context switch done`)
            await waitForDocumentReady(elapsed)
            return
        } catch (e: unknown) {
            const msg = e instanceof Error ? e.message : String(e)
            console.log(
                `[switchToWebView +${elapsed()}s] Attempt ${attempt} failed: ${msg}`,
            )
            if (attempt === maxAttempts) throw e
            await driver.pause(3_000)
        }
    }
}

export async function switchToNative(): Promise<void> {
    await driver.switchContext('NATIVE_APP')
}

// On Android the context list can contain more than one WEBVIEW: our own app
// (`WEBVIEW_me.finanze`) plus unrelated system webviews such as the Google
// quicksearch box (`WEBVIEW_com.google.android.googlequicksearchbox:search`).
// Picking the wrong one yields "chrome not reachable". Always prefer the app's
// own webview and never select a known system webview.
function pickAppWebview(contexts: string[]): string | undefined {
    const webviews = contexts.filter((c) => c.startsWith('WEBVIEW'))
    const appWebview = webviews.find((c) => c.toLowerCase().includes('finanze'))
    if (appWebview) return appWebview
    return webviews.find(
        (c) =>
            !c.includes('googlequicksearchbox') &&
            !c.includes('com.android.chrome'),
    )
}

// After switching context the WEBVIEW can briefly point at a blank/not-yet
// navigated document (especially on iOS). Wait until the HTML document has
// finished loading, then log what is actually on screen so that, when the app
// shell loads but the SPA never renders (e.g. a stuck Pyodide boot), CI logs
// show the real cause instead of just a generic element timeout.
async function waitForDocumentReady(elapsed: () => string): Promise<void> {
    try {
        await driver.waitUntil(
            async () => {
                try {
                    const state = await driver.execute(
                        () => document.readyState,
                    )
                    return state === 'complete' || state === 'interactive'
                } catch {
                    return false
                }
            },
            { timeout: 30_000, interval: 1_000 },
        )
        console.log(`[switchToWebView +${elapsed()}s] Document ready`)
    } catch {
        console.log(
            `[switchToWebView +${elapsed()}s] Document readiness wait timed out, continuing`,
        )
    }

    try {
        const info = (await driver.execute(() => ({
            url: location.href,
            title: document.title,
            hasUsername: !!document.querySelector('#username'),
            bodyText: (document.body?.innerText || '').slice(0, 300),
        }))) as {
            url: string
            title: string
            hasUsername: boolean
            bodyText: string
        }
        console.log(
            `[switchToWebView +${elapsed()}s] page url=${info.url} title=${JSON.stringify(
                info.title,
            )} hasUsername=${info.hasUsername} bodyText=${JSON.stringify(
                info.bodyText,
            )}`,
        )
    } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e)
        console.log(
            `[switchToWebView +${elapsed()}s] page diagnostics failed: ${msg}`,
        )
    }
}
