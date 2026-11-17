import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { TEST_PASSWORD, TEST_USER } from './constants.js'
import { switchToWebView } from './webview.js'

const APP_PACKAGE = 'me.finanze'
const STATEMENTS = join(
    import.meta.dirname,
    '..',
    '..',
    '..',
    '..',
    'tests',
    'resources',
    'import',
    'statements',
)

export interface UploadFile {
    name: string
    type: string
    content: string
}

export interface ExportedFile {
    name: string
    content: string
}

type ExportResult = ExportedFile | { error: string }

const literal = (text: string) =>
    text.includes('"') ? `'${text}'` : `"${text}"`

export const HEADING_XPATH = (text: string) =>
    `//*[self::h1 or self::h2 or self::h3 or self::h4][contains(text(),${literal(text)})]`

export const TEXT_XPATH = (text: string) =>
    `//*[normalize-space(text())=${literal(text)}]`

export const BUTTON_XPATH = (text: string) =>
    `.//button[normalize-space()=${literal(text)}]`

export function overlay(title: string) {
    return $(
        `(//div[contains(concat(" ", @class, " "), " fixed ") and contains(concat(" ", @class, " "), " inset-0 ")][.${TEXT_XPATH(title)}])[last()]`,
    )
}

export async function blurActiveElement(): Promise<void> {
    const blurred = await browser.execute(() => {
        const active = document.activeElement as HTMLElement | null
        if (
            active &&
            (active.tagName === 'INPUT' ||
                active.tagName === 'TEXTAREA' ||
                active.isContentEditable)
        ) {
            active.blur()
            return true
        }
        return false
    })
    if (!blurred) return

    await browser
        .waitUntil(
            () =>
                browser.execute(
                    () =>
                        !window.visualViewport ||
                        window.visualViewport.height >=
                            window.innerHeight * 0.85,
                ),
            { timeout: 1_000, interval: 100 },
        )
        .catch(() => undefined)
    await browser.pause(150)
}

export async function setInputValue(
    selector: string,
    value: string,
    timeout = 10_000,
): Promise<void> {
    const field = $(selector)
    await field.waitForDisplayed({ timeout })

    await browser.execute((sel: string) => {
        const candidates = Array.from(
            document.querySelectorAll<HTMLInputElement>(sel),
        )
        const input = (candidates.find(
            el => el.offsetParent !== null || el.getClientRects().length > 0,
        ) ?? candidates[0]) as
            | (HTMLInputElement & {
                  _valueTracker?: { setValue: (v: string) => void }
              })
            | undefined
        if (!input || input.value === '') return
        const prev = input.value
        const nativeSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype,
            'value',
        )?.set
        if (nativeSetter) {
            nativeSetter.call(input, '')
        } else {
            input.value = ''
        }
        input._valueTracker?.setValue(prev)
        input.dispatchEvent(new Event('input', { bubbles: true }))
    }, selector)

    await $(selector).setValue(value)

    await browser.waitUntil(
        async () =>
            browser.execute(
                (sel: string, expected: string) => {
                    const candidates = Array.from(
                        document.querySelectorAll<HTMLInputElement>(sel),
                    )
                    const input = (candidates.find(
                        el =>
                            el.offsetParent !== null ||
                            el.getClientRects().length > 0,
                    ) ?? candidates[0]) as
                        | (HTMLInputElement & {
                              _valueTracker?: {
                                  getValue?: () => string
                                  setValue: (v: string) => void
                              }
                          })
                        | undefined
                    if (!input) return false
                    if (
                        input.value === expected &&
                        (!input._valueTracker?.getValue ||
                            input._valueTracker.getValue() === expected)
                    ) {
                        return true
                    }
                    const prev =
                        input.value === expected ? '' : input.value
                    const nativeSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype,
                        'value',
                    )?.set
                    if (nativeSetter) {
                        nativeSetter.call(input, expected)
                    } else {
                        input.value = expected
                    }
                    input._valueTracker?.setValue(prev)
                    input.dispatchEvent(new Event('input', { bubbles: true }))
                    input.dispatchEvent(new Event('change', { bubbles: true }))
                    return input.value === expected
                },
                selector,
                value,
            ),
        {
            timeout: 5_000,
            interval: 150,
            timeoutMsg: `Failed to set expected value on ${selector}`,
        },
    )
}

export async function submitLoginForm(timeout = 5_000): Promise<void> {
    await blurActiveElement()
    const submit = $('button[type="submit"]')
    await submit.waitForDisplayed({ timeout })
    await submit.scrollIntoView({ block: 'center' })
    await submit.waitForClickable({ timeout })

    await browser.execute(() => {
        const win = window as unknown as { __e2eFormSubmitted?: boolean }
        win.__e2eFormSubmitted = false
        const btn = document.querySelector(
            'button[type="submit"]',
        ) as HTMLButtonElement | null
        const form = btn?.closest('form')
        form?.addEventListener(
            'submit',
            () => {
                win.__e2eFormSubmitted = true
            },
            { once: true, capture: true },
        )
    })

    await submit.click()

    let submitted = await browser.execute(() =>
        Boolean(
            (window as unknown as { __e2eFormSubmitted?: boolean })
                .__e2eFormSubmitted,
        ),
    )
    if (!submitted) {
        await browser.pause(150)
        submitted = await browser.execute(() =>
            Boolean(
                (window as unknown as { __e2eFormSubmitted?: boolean })
                    .__e2eFormSubmitted,
            ),
        )
    }
    if (!submitted) {
        await browser.execute(() => {
            const win = window as unknown as { __e2eFormSubmitted?: boolean }
            const btn = document.querySelector(
                'button[type="submit"]',
            ) as HTMLButtonElement | null
            const form = btn?.closest('form')
            if (!form || !btn || btn.disabled) return
            if (typeof form.requestSubmit === 'function') {
                try {
                    form.requestSubmit(btn)
                } catch {
                    // Fall through to synthetic submit event
                }
            }
            if (!win.__e2eFormSubmitted) {
                form.dispatchEvent(
                    new Event('submit', { bubbles: true, cancelable: true }),
                )
            }
        })
    }
}

export async function ensureSignedIn(): Promise<void> {
    await switchToWebView()
    const password = $('#password')
    await password.waitForDisplayed({ timeout: 90_000 })
    if (await $('#username').isDisplayed()) {
        await setInputValue('#username', TEST_USER)
        await setInputValue('#password', TEST_PASSWORD)
        await setInputValue('#repeatPassword', TEST_PASSWORD)
    } else {
        await setInputValue('#password', TEST_PASSWORD)
    }
    await submitLoginForm(5_000)
    await browser.waitUntil(
        async () => !(await browser.getUrl()).includes('/login'),
        { timeout: 60_000, timeoutMsg: 'Still on /login after signing in' },
    )
    await $(HEADING_XPATH('Summary')).waitForDisplayed({ timeout: 30_000 })
}

export async function openMoreMenuPage(
    name: string,
    heading = name,
): Promise<void> {
    const more = $('button[aria-label="More"]')
    await more.waitForDisplayed({ timeout: 10_000 })
    await more.click()
    const entry = $(`//button[normalize-space()=${literal(name)}]`)
    await entry.waitForDisplayed({ timeout: 5_000 })
    await entry.click()
    await $(HEADING_XPATH(heading)).waitForDisplayed({ timeout: 15_000 })
}

export async function selectTab(name: string): Promise<void> {
    const tab = $(`//*[@role="tab"][normalize-space()=${literal(name)}]`)
    await tab.waitForDisplayed({ timeout: 10_000 })
    await tab.click()
}

export async function clickIn(
    scope: ReturnType<typeof $>,
    text: string,
    timeout = 10_000,
): Promise<void> {
    await blurActiveElement()
    const button = scope.$(BUTTON_XPATH(text))
    await button.waitForClickable({ timeout })
    await button.click()
}

export async function waitForText(text: string, timeout = 15_000) {
    await $(TEXT_XPATH(text)).waitForDisplayed({ timeout })
}

export async function confirmImport(
    preview: ReturnType<typeof overlay>,
): Promise<void> {
    await clickIn(preview, 'Import data')
    // Slow polling misses the 3s success toast; both dialogs only close once the import is stored.
    await preview.waitForDisplayed({ reverse: true, timeout: 90_000 })
    await overlay('Import data from file').waitForDisplayed({
        reverse: true,
        timeout: 15_000,
    })
}

export function textFile(name: string, type: string, text: string): UploadFile {
    return { name, type, content: Buffer.from(text).toString('base64') }
}

export function statementFile(name: string): UploadFile {
    return {
        name,
        type: 'application/pdf',
        content: readFileSync(join(STATEMENTS, name)).toString('base64'),
    }
}

export async function setInputFile(
    selector: string,
    file: UploadFile,
): Promise<void> {
    await browser.execute(
        (
            inputSelector: string,
            name: string,
            type: string,
            content: string,
        ) => {
            const input = document.querySelector(
                inputSelector,
            ) as HTMLInputElement | null
            if (!input) throw new Error(`Missing file input ${inputSelector}`)
            const binary = atob(content)
            const bytes = new Uint8Array(binary.length)
            for (let i = 0; i < binary.length; i++) {
                bytes[i] = binary.charCodeAt(i)
            }
            const transfer = new DataTransfer()
            transfer.items.add(new File([bytes], name, { type }))
            input.files = transfer.files
            input.dispatchEvent(new Event('change', { bubbles: true }))
        },
        selector,
        file.name,
        file.type,
        file.content,
    )
}

export async function dismissShareSheet(timeout = 15_000): Promise<void> {
    const webview = await driver.getAppiumContext()
    await driver.switchAppiumContext('NATIVE_APP')
    try {
        if (driver.isAndroid) {
            const opened = await browser
                .waitUntil(
                    async () =>
                        (await driver.getCurrentPackage()) !== APP_PACKAGE,
                    { timeout, interval: 500 },
                )
                .catch(() => false)
            if (opened) await driver.back()
        } else {
            const sheet = $('~ActivityListView')
            const opened = await sheet
                .waitForExist({ timeout })
                .catch(() => false)
            if (opened) {
                // The iOS share sheet has no close button; tap above it and swipe it down if the tap is swallowed.
                const { width } = await driver.getWindowSize()
                const dismissed = (wait: number) =>
                    sheet.waitForExist({ reverse: true, timeout: wait }).then(
                        () => true,
                        () => false,
                    )
                await browser.waitUntil(
                    async () => {
                        if (!(await sheet.isExisting())) return true
                        await driver.execute('mobile: tap', {
                            x: width / 2,
                            y: 80,
                        })
                        if (await dismissed(5_000)) return true
                        const element = await sheet
                        await driver
                            .execute('mobile: swipe', {
                                direction: 'down',
                                elementId: element.elementId,
                            })
                            .catch(() => undefined)
                        return dismissed(5_000)
                    },
                    {
                        timeout,
                        interval: 1_000,
                        timeoutMsg: 'iOS share sheet was not dismissed',
                    },
                )
            }
        }
    } finally {
        await driver.switchAppiumContext(String(webview))
    }
}

export async function readLatestExport(
    extension: string,
): Promise<ExportedFile> {
    await browser.setTimeout({ script: 30_000 })
    const result = await browser.executeAsync<ExportResult, [string]>(
        (ext: string, done: (value?: ExportResult) => void) => {
            const filesystem = (window as any).Capacitor?.Plugins?.Filesystem
            if (!filesystem) {
                done({ error: 'Filesystem plugin unavailable' })
                return
            }
            filesystem
                .readdir({ path: 'finanze', directory: 'DOCUMENTS' })
                .then(
                    ({
                        files,
                    }: {
                        files: { name: string; mtime?: number | string }[]
                    }) => {
                        const latest = files
                            .filter((file) => file.name.endsWith(ext))
                            .sort(
                                (a, b) => Number(b.mtime) - Number(a.mtime),
                            )[0]
                        if (!latest) {
                            done({ error: `No exported ${ext} file` })
                            return
                        }
                        return filesystem
                            .readFile({
                                path: `finanze/${latest.name}`,
                                directory: 'DOCUMENTS',
                                encoding: 'utf8',
                            })
                            .then(({ data }: { data: string }) =>
                                done({ name: latest.name, content: data }),
                            )
                    },
                )
                .catch((error: unknown) => done({ error: String(error) }))
        },
        extension,
    )
    if (!result || 'error' in result) {
        throw new Error(result?.error ?? 'Export could not be read')
    }
    return result
}
