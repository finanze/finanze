import { expect, type Page, type Request } from '@playwright/test'
import { test } from '../../fixtures/auth'

const INTEGRATION_ID = 'GOOGLE_SHEETS'
const PAYLOAD = { client_id: 'e2e-client-id', client_secret: 'e2e-secret' }
const RETURN_ROUTE = `#/entities?tab=providers&focus=${INTEGRATION_ID}`

interface OAuthMocks {
    connectBodies: unknown[]
    completeBodies: unknown[]
}

async function mockGoogleOAuth(
    page: Page,
    callbackParams: Record<string, string>,
    complete: { status: number; body?: unknown },
): Promise<OAuthMocks> {
    const mocks: OAuthMocks = { connectBodies: [], completeBodies: [] }
    let completed = false

    await page.route(
        (url) => url.pathname === `/api/v1/integrations/${INTEGRATION_ID}`,
        async (route) => {
            const request = route.request()
            if (request.method() !== 'POST') return route.fallback()
            mocks.connectBodies.push(request.postDataJSON())
            const appUrl = new URL(page.url())
            const query = new URLSearchParams({
                integration_oauth: INTEGRATION_ID,
                ...callbackParams,
            })
            await route.fulfill({
                status: 200,
                json: {
                    link: `${appUrl.origin}${appUrl.pathname}?${query}${RETURN_ROUTE}`,
                },
            })
        },
    )

    await page.route(
        (url) =>
            url.pathname ===
            `/api/v1/integrations/${INTEGRATION_ID}/oauth/complete`,
        async (route) => {
            mocks.completeBodies.push(route.request().postDataJSON())
            completed = complete.status < 400
            if (complete.body === undefined) {
                return route.fulfill({ status: complete.status })
            }
            return route.fulfill({
                status: complete.status,
                json: complete.body,
            })
        },
    )

    await page.route(
        (url) => url.pathname === '/api/v1/integrations',
        async (route) => {
            const request: Request = route.request()
            if (request.method() !== 'GET' || !completed) {
                return route.fallback()
            }
            const response = await route.fetch()
            const body = await response.json()
            body.integrations = body.integrations.map(
                (integration: { id: string }) =>
                    integration.id === INTEGRATION_ID
                        ? { ...integration, status: 'ON' }
                        : integration,
            )
            return route.fulfill({ response, json: body })
        },
    )

    return mocks
}

async function startGoogleSheetsSetup(page: Page) {
    await page.getByRole('button', { name: 'Integrations' }).click()
    await page.getByRole('tab', { name: 'Providers' }).click()

    const card = page.getByTestId(`integration-card-${INTEGRATION_ID}`)
    await card.getByText('Google Sheets', { exact: true }).click()
    await expect(card.getByText('Disabled', { exact: true })).toBeVisible()
    await expect(card.getByText('Use desktop app')).toHaveCount(0)

    await card.locator(`#${INTEGRATION_ID}-client_id`).fill(PAYLOAD.client_id)
    await card
        .locator(`#${INTEGRATION_ID}-client_secret`)
        .fill(PAYLOAD.client_secret)
    await card.getByRole('button', { name: 'Setup' }).click()
}

test.describe('Google Sheets integration on web', () => {
    test('connects through the Google authorization redirect', async ({
        authenticatedPage: page,
    }) => {
        const mocks = await mockGoogleOAuth(
            page,
            { code: 'auth-code', state: 'relay-state' },
            { status: 204 },
        )

        await startGoogleSheetsSetup(page)

        await expect(
            page.getByText('Google Sheets integration enabled successfully'),
        ).toBeVisible({ timeout: 20_000 })

        const appUrl = new URL(page.url())
        expect(mocks.connectBodies).toEqual([
            {
                payload: PAYLOAD,
                completion_url: `${appUrl.origin}${appUrl.pathname}?integration_oauth=${INTEGRATION_ID}${RETURN_ROUTE}`,
            },
        ])
        expect(mocks.completeBodies).toEqual([
            { state: 'relay-state', code: 'auth-code', error: null },
        ])
        await expect(page).not.toHaveURL(/integration_oauth|auth-code/)
        await expect(page).toHaveURL(/#\/entities\?tab=providers/)

        const card = page.getByTestId(`integration-card-${INTEGRATION_ID}`)
        await expect(card.getByText('Enabled', { exact: true })).toBeVisible()
    })

    test('shows an error when the authorization is denied', async ({
        authenticatedPage: page,
    }) => {
        const mocks = await mockGoogleOAuth(
            page,
            { error: 'access_denied', state: 'relay-state' },
            { status: 400, body: { code: 'AUTHORIZATION_DENIED' } },
        )

        await startGoogleSheetsSetup(page)

        await expect(
            page.getByText(
                'Access to Google Sheets was denied or the required permissions were not granted.',
            ),
        ).toBeVisible({ timeout: 20_000 })
        expect(mocks.completeBodies).toEqual([
            { state: 'relay-state', code: null, error: 'access_denied' },
        ])
        await expect(page).not.toHaveURL(/integration_oauth|access_denied/)

        const card = page.getByTestId(`integration-card-${INTEGRATION_ID}`)
        await expect(card.getByText('Disabled', { exact: true })).toBeVisible()
    })
})
