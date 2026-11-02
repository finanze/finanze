import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'

const INTEGRATION_ID = 'CLAUDE_AGENT'
const CLI_PATH = '/usr/local/bin/claude'

async function mockSetup(
    page: Page,
    response: { status: number; body: unknown },
): Promise<unknown[]> {
    const bodies: unknown[] = []
    let connected = false

    await page.route(
        (url) => url.pathname === `/api/v1/integrations/${INTEGRATION_ID}`,
        async (route) => {
            const request = route.request()
            if (request.method() !== 'POST') return route.fallback()
            bodies.push(request.postDataJSON())
            connected = response.status < 400
            await route.fulfill({
                status: response.status,
                json: response.body,
            })
        },
    )

    await page.route(
        (url) => url.pathname === '/api/v1/integrations',
        async (route) => {
            if (route.request().method() !== 'GET' || !connected) {
                return route.fallback()
            }
            const fetched = await route.fetch()
            const body = await fetched.json()
            body.integrations = body.integrations.map(
                (integration: { id: string }) =>
                    integration.id === INTEGRATION_ID
                        ? { ...integration, status: 'ON' }
                        : integration,
            )
            return route.fulfill({ response: fetched, json: body })
        },
    )

    return bodies
}

async function fillClaudeSetup(page: Page, cliPath?: string) {
    await page.getByRole('button', { name: 'Integrations' }).click()
    await page.getByRole('tab', { name: 'Providers' }).click()

    const card = page.getByTestId(`integration-card-${INTEGRATION_ID}`)
    await card.getByText('Claude Agent', { exact: true }).click()
    await expect(card.getByText('Disabled', { exact: true })).toBeVisible()
    await expect(
        card.getByText(
            /through Claude Code installed and signed in on this computer/,
        ),
    ).toBeVisible()
    await expect(card.locator(`#${INTEGRATION_ID}-api_key`)).toHaveCount(0)

    if (cliPath) {
        await card.locator(`#${INTEGRATION_ID}-cli_path`).fill(cliPath)
    }
    await card.getByRole('button', { name: 'Setup' }).click()
    return card
}

test.describe('Claude Agent integration', () => {
    test('connects with the signed-in Claude Code at a custom path', async ({
        authenticatedPage: page,
    }) => {
        const bodies = await mockSetup(page, { status: 200, body: {} })

        const card = await fillClaudeSetup(page, CLI_PATH)

        await expect(
            page.getByText('Claude Agent integration enabled successfully'),
        ).toBeVisible({ timeout: 20_000 })
        await expect(card.getByText('Enabled', { exact: true })).toBeVisible()
        expect(bodies).toEqual([{ payload: { cli_path: CLI_PATH } }])
    })

    test('explains when Claude Code is not signed in', async ({
        authenticatedPage: page,
    }) => {
        const bodies = await mockSetup(page, {
            status: 400,
            body: { code: 'RUNTIME_NOT_AUTHENTICATED' },
        })

        const card = await fillClaudeSetup(page)

        await expect(
            page.getByText(
                'The program required by Claude Agent is not signed in. Sign in to it on this computer and try again.',
            ),
        ).toBeVisible({ timeout: 20_000 })
        await expect(card.getByText('Disabled', { exact: true })).toBeVisible()
        expect(bodies).toEqual([{ payload: {} }])
    })
})
