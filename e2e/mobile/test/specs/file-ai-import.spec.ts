import {
    deviceBaseUrl,
    startAIMockServer,
    type AIMockServer,
} from '../helpers/ai-mock-server.js'
import {
    clickIn,
    ensureSignedIn,
    openMoreMenuPage,
    overlay,
    selectTab,
    setInputFile,
    statementFile,
    waitForText,
} from '../helpers/ui.js'

const PNG =
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
const MODEL = 'mobile-vision'
const PDF_NO_TEXT =
    'This PDF contains scanned images or vector outlines without selectable text. Export the statement as CSV, Excel, or a text-based PDF.'
const SCANNED_PAGES = 4
const id = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
const receipt = `Mobile Coffee ${id}`

function today() {
    const date = new Date()
    const pad = (value: number) => String(value).padStart(2, '0')
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

const byTestId = (testId: string) => $(`[data-testid="${testId}"]`)

async function connectMockProvider(server: AIMockServer) {
    const integrations = $('button[aria-label="Integrations"]')
    await integrations.waitForClickable({ timeout: 10_000 })
    await integrations.click()
    await selectTab('Providers')

    const card = byTestId('integration-card-OPENAI_COMPATIBLE')
    await card.waitForDisplayed({ timeout: 30_000 })
    await card.scrollIntoView()
    await card.$('div.cursor-pointer').click()
    const baseUrl = $('#OPENAI_COMPATIBLE-base_url')
    await baseUrl.waitForDisplayed({ timeout: 10_000 })
    await baseUrl.setValue(deviceBaseUrl(server.port))
    await clickIn(card, 'Setup')
    await byTestId('integration-server-details-OPENAI_COMPATIBLE').waitForExist(
        {
            timeout: 60_000,
        },
    )

    const settingsLink = byTestId('ai-models-settings-link')
    await settingsLink.scrollIntoView()
    await settingsLink.click()
    const models = byTestId('ai-models-card')
    await models.waitForDisplayed({ timeout: 15_000 })
    await byTestId('ai-models-add-provider').click()
    await byTestId('ai-models-provider-option-OPENAI_COMPATIBLE').click()
    const option = $(
        `//*[@data-testid="ai-models-model-options"]//label[.//*[normalize-space(text())="${MODEL}"]]`,
    )
    await option.waitForDisplayed({ timeout: 60_000 })
    await option.click()
    const save = byTestId('ai-models-save')
    await save.waitForClickable({ timeout: 10_000 })
    await save.click()
    await save.waitForDisplayed({ reverse: true, timeout: 30_000 })
}

describe('AI file import', () => {
    let server: AIMockServer

    before(async () => {
        server = await startAIMockServer(
            [MODEL],
            [
                {
                    ref: null,
                    name: receipt,
                    amount: '-4.20',
                    currency: 'EUR',
                    type: null,
                    date: today(),
                },
            ],
        )
        await ensureSignedIn()
        await connectMockProvider(server)
        await openMoreMenuPage('Export & Import')
    })

    after(async () => {
        await server?.close()
    })

    it('extracts a receipt image with AI and imports the reviewed rows', async () => {
        await selectTab('Import')
        const importButton = $('//button[normalize-space()="Import..."]')
        await importButton.waitForClickable({ timeout: 15_000 })
        await importButton.click()
        const dialog = overlay('Import data from file')
        await dialog.waitForDisplayed({ timeout: 10_000 })
        await clickIn(dialog, 'Transactions')
        await clickIn(dialog, 'Account')
        await setInputFile('#file-import-input', {
            name: 'receipt.png',
            type: 'image/png',
            content: PNG,
        })

        await browser.waitUntil(
            async () =>
                (await $('#file-import-use-ai').getAttribute('data-state')) ===
                'checked',
            { timeout: 10_000, timeoutMsg: 'AI extraction was not enabled' },
        )
        const createEntity = dialog.$(
            './/button[@title="Create new entity..."]',
        )
        await createEntity.waitForClickable({ timeout: 5_000 })
        await createEntity.click()
        await dialog.$('#file-import-entity-input').setValue(`Mobile AI ${id}`)
        await clickIn(dialog, 'Preview')

        const preview = overlay('Review simulated import')
        await preview.waitForDisplayed({ timeout: 120_000 })
        await expect(byTestId('import-preview-ai')).toHaveText(
            expect.stringContaining(MODEL),
        )
        await preview
            .$(`.//*[contains(normalize-space(), "${receipt}")]`)
            .waitForExist({ timeout: 10_000 })
        await clickIn(preview, 'Import data')

        await waitForText(
            'File imported successfully. Refreshing your data...',
            60_000,
        )
        expect(server.calls).toHaveLength(1)
        const messages = server.calls[0].body.messages as {
            content: unknown
        }[]
        const parts = messages.at(-1)!.content as { type: string }[]
        expect(parts.map((part) => part.type)).toContain('image_url')
    })

    it('renders every page of a scanned statement PDF on the device and reads them with AI', async () => {
        const firstCall = server.calls.length
        const movement = (page: number) => `Mobile Scan ${id} page ${page}`
        server.setRows((call) => [
            {
                ref: null,
                name: movement(call - firstCall + 1),
                amount: `-${call - firstCall + 1}.50`,
                currency: 'EUR',
                type: null,
                date: today(),
            },
        ])

        await selectTab('Import')
        const importButton = $('//button[normalize-space()="Import..."]')
        await importButton.waitForClickable({ timeout: 15_000 })
        await importButton.click()
        const dialog = overlay('Import data from file')
        await dialog.waitForDisplayed({ timeout: 10_000 })
        await clickIn(dialog, 'Transactions')
        await clickIn(dialog, 'Account')
        await setInputFile(
            '#file-import-input',
            statementFile('myinvestor_scanned.pdf'),
        )
        await waitForText(PDF_NO_TEXT, 90_000)

        await $('#file-import-use-ai').click()
        await browser.waitUntil(
            async () =>
                (await $('#file-import-use-ai').getAttribute('data-state')) ===
                'checked',
            { timeout: 10_000, timeoutMsg: 'AI extraction was not enabled' },
        )
        const createEntity = dialog.$(
            './/button[@title="Create new entity..."]',
        )
        await createEntity.waitForClickable({ timeout: 5_000 })
        await createEntity.click()
        await dialog
            .$('#file-import-entity-input')
            .setValue(`Mobile Scan ${id}`)
        await clickIn(dialog, 'Preview')

        const preview = overlay('Review simulated import')
        await preview.waitForDisplayed({ timeout: 180_000 })
        await preview
            .$(
                `.//*[contains(normalize-space(), "${SCANNED_PAGES} transactions")]`,
            )
            .waitForDisplayed({ timeout: 10_000 })
        await preview
            .$(`.//*[contains(normalize-space(), "${movement(1)}")]`)
            .waitForExist({ timeout: 10_000 })
        await clickIn(preview, 'Import data')
        await waitForText(
            'File imported successfully. Refreshing your data...',
            60_000,
        )

        const calls = server.calls.slice(firstCall)
        expect(calls).toHaveLength(SCANNED_PAGES)
        for (const call of calls) {
            const messages = call.body.messages as { content: unknown }[]
            const images = (
                messages.at(-1)!.content as {
                    type: string
                    image_url?: { url: string }
                }[]
            ).filter((part) => part.type === 'image_url')
            expect(images).toHaveLength(1)
            expect(images[0].image_url!.url).toMatch(
                /^data:image\/(png|jpeg|webp);base64,/,
            )
            expect(images[0].image_url!.url.length).toBeGreaterThan(20_000)
        }
    })
})
