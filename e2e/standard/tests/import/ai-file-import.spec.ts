import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { BACKEND_URL } from '../../helpers/constants'
import {
    chatCompletion,
    startAIMockServer,
    type AIMockServer,
} from '../../helpers/ai-mock-server'
import en from '../../../../frontend/app/src/i18n/locales/en.json' with { type: 'json' }

const PNG = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
    'base64',
)
const INTEGRATION = 'OPENAI_COMPATIBLE'

function uid() {
    return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
}

function today() {
    const date = new Date()
    const pad = (value: number) => String(value).padStart(2, '0')
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

async function backend(path: string, method: string, body?: unknown) {
    const response = await fetch(`${BACKEND_URL}${path}`, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
    })
    expect(response.ok).toBeTruthy()
}

async function useMockModel(server: AIMockServer, model: string) {
    await backend(`/api/v1/integrations/${INTEGRATION}`, 'POST', {
        payload: { base_url: server.url },
    })
    await backend('/api/v1/settings', 'POST', {
        ai: { providers: [{ provider: INTEGRATION, model }] },
    })
}

function overlay(page: Page, text: string) {
    return page.locator('.fixed.inset-0').filter({ hasText: text }).last()
}

async function openReceiptImport(page: Page, entity: string) {
    await page.getByRole('button', { name: 'Export & Import' }).click()
    await page.getByRole('tab', { name: 'Import' }).click()
    await page.getByRole('button', { name: 'Import...' }).click()
    const dialog = overlay(page, en.export.fileImport.dialogTitle)
    await expect(dialog).toBeVisible({ timeout: 5_000 })
    await dialog
        .getByRole('button', { name: 'Transactions', exact: true })
        .click()
    await dialog.getByRole('button', { name: 'Account', exact: true }).click()
    await dialog.locator('#file-import-input').setInputFiles({
        name: 'receipt.png',
        mimeType: 'image/png',
        buffer: PNG,
    })
    await expect(dialog.locator('#file-import-use-ai')).toHaveAttribute(
        'data-state',
        'checked',
    )
    await dialog.getByTitle('Create new entity...').click()
    await dialog.locator('#file-import-entity-input').fill(entity)
    return dialog
}

test.describe('AI file import', () => {
    let server: AIMockServer

    test.beforeEach(async () => {
        server = await startAIMockServer([])
    })

    test.afterEach(async () => {
        await backend('/api/v1/settings', 'POST', { ai: { providers: [] } })
        await backend(`/api/v1/integrations/${INTEGRATION}`, 'DELETE')
        await server.close()
    })

    test('extracts a receipt in background and imports the reviewed preview', async ({
        authenticatedPage: page,
    }) => {
        const id = uid()
        const name = `E2E AI Coffee ${id}`
        await useMockModel(server, `vision-${id}`)
        let release: () => void = () => {}
        const pending = new Promise<void>((resolve) => {
            release = resolve
        })
        server.setReply(async () => {
            await pending
            return chatCompletion({
                rows: [
                    {
                        ref: null,
                        name,
                        amount: '-4.20',
                        currency: 'EUR',
                        type: null,
                        date: today(),
                        entity: null,
                    },
                ],
            })
        })

        const dialog = await openReceiptImport(page, `E2E AI Bank ${id}`)
        await dialog
            .getByRole('button', { name: 'Preview', exact: true })
            .click()
        await dialog.getByTestId('file-import-background').click()
        await expect(dialog).toBeHidden()
        await expect(page.getByTestId('file-import-running')).toBeVisible()

        release()
        await page
            .getByRole('button', {
                name: en.export.fileImport.background.review,
            })
            .last()
            .click()
        const preview = overlay(page, 'Review simulated import')
        await expect(preview).toBeVisible({ timeout: 15_000 })
        await expect(preview.getByText(name).first()).toBeVisible()

        await preview.getByRole('button', { name: 'Import data' }).click()
        await expect(
            page.getByText(en.export.fileImport.toast.success),
        ).toBeVisible({ timeout: 15_000 })
        expect(server.calls).toHaveLength(1)
        const content = (
            server.calls[0].body.messages as { content: unknown }[]
        ).at(-1)!.content as { type: string }[]
        expect(content.map((part) => part.type)).toContain('image_url')
    })

    test('reports when no AI model can process the file', async ({
        authenticatedPage: page,
    }) => {
        const id = uid()
        await useMockModel(server, `broken-${id}`)
        server.setReply(() => ({ status: 500, body: { error: 'no images' } }))

        const dialog = await openReceiptImport(page, `E2E AI Bank ${id}`)
        await dialog
            .getByRole('button', { name: 'Preview', exact: true })
            .click()

        await expect(page.getByText(en.errors.AI_UNAVAILABLE)).toBeVisible({
            timeout: 15_000,
        })
        await expect(dialog).toBeVisible()
        expect(server.calls).toHaveLength(1)
    })
})
