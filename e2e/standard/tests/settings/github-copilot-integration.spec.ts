import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'

const INTEGRATION_ID = 'GITHUB_COPILOT'
const VERIFICATION_URI = 'https://github.com/login/device'
const USER_CODE = 'E2E1-2345'

interface DeviceMocks {
    connectBodies: unknown[]
    pollBodies: unknown[]
}

async function mockDeviceFlow(
    page: Page,
    pollResponses: { status: number; body: unknown }[],
): Promise<DeviceMocks> {
    const mocks: DeviceMocks = { connectBodies: [], pollBodies: [] }
    let connected = false

    await page.route(
        (url) => url.pathname === `/api/v1/integrations/${INTEGRATION_ID}`,
        async (route) => {
            const request = route.request()
            if (request.method() !== 'POST') return route.fallback()
            mocks.connectBodies.push(request.postDataJSON())
            await route.fulfill({
                status: 200,
                json: {
                    device: {
                        flow_id: 'e2e-flow',
                        user_code: USER_CODE,
                        verification_uri: VERIFICATION_URI,
                        expires_in: 900,
                        interval: 1,
                    },
                },
            })
        },
    )

    await page.route(
        (url) =>
            url.pathname ===
            `/api/v1/integrations/${INTEGRATION_ID}/device/poll`,
        async (route) => {
            mocks.pollBodies.push(route.request().postDataJSON())
            const response = pollResponses.shift() ?? {
                status: 200,
                body: { status: 'PENDING', interval: 1 },
            }
            connected =
                (response.body as { status?: string }).status === 'CONNECTED'
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

async function startCopilotSetup(page: Page) {
    await page.getByRole('button', { name: 'Integrations' }).click()
    await page.getByRole('tab', { name: 'Providers' }).click()

    const card = page.getByTestId(`integration-card-${INTEGRATION_ID}`)
    await card.getByText('GitHub Copilot', { exact: true }).click()
    await expect(card.getByText('Disabled', { exact: true })).toBeVisible()
    await expect(
        card.getByText(/one-time code to sign in with your GitHub Copilot/),
    ).toBeVisible()

    await card.getByRole('button', { name: 'Setup' }).click()
    await expect(card.getByText(USER_CODE)).toBeVisible()
    return card
}

test.describe('GitHub Copilot integration', () => {
    test('connects with a device code', async ({ authenticatedPage: page }) => {
        const mocks = await mockDeviceFlow(page, [
            { status: 200, body: { status: 'PENDING', interval: 1 } },
            { status: 200, body: { status: 'CONNECTED' } },
        ])
        await page.context().route('https://github.com/**', (route) =>
            route.fulfill({
                status: 200,
                contentType: 'text/html',
                body: '<html><body>GitHub device login</body></html>',
            }),
        )

        const card = await startCopilotSetup(page)
        await expect(
            card.getByText(
                'Enter this code at github.com to authorize Finanze:',
            ),
        ).toBeVisible()

        const popupPromise = page.context().waitForEvent('page')
        await card
            .getByRole('button', { name: 'Copy code and open github.com' })
            .click()
        const popup = await popupPromise
        await expect(popup).toHaveURL(VERIFICATION_URI)
        await popup.close()

        await expect(
            page.getByText('GitHub Copilot integration enabled successfully'),
        ).toBeVisible({ timeout: 20_000 })
        await expect(card.getByText('Enabled', { exact: true })).toBeVisible()
        await expect(card.getByText(USER_CODE)).toHaveCount(0)

        expect(mocks.connectBodies).toEqual([{ payload: {} }])
        expect(mocks.pollBodies).toEqual([
            { flow_id: 'e2e-flow' },
            { flow_id: 'e2e-flow' },
        ])
    })

    test('shows an error when the authorization is denied', async ({
        authenticatedPage: page,
    }) => {
        await mockDeviceFlow(page, [
            { status: 400, body: { code: 'AUTHORIZATION_DENIED' } },
        ])

        const card = await startCopilotSetup(page)

        await expect(
            page.getByText(
                'Access to GitHub Copilot was denied or the required permissions were not granted.',
            ),
        ).toBeVisible({ timeout: 20_000 })
        await expect(card.getByText(USER_CODE)).toHaveCount(0)
        await expect(card.getByText('Disabled', { exact: true })).toBeVisible()
        await expect(card.getByRole('button', { name: 'Setup' })).toBeVisible()
    })
})
