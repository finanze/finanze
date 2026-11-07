import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'

const INTEGRATION_ID = 'CHATGPT'
const RETURN_ROUTE = `#/entities?tab=providers&focus=${INTEGRATION_ID}`
const AUTHORIZE_URL =
    'https://auth.openai.com/api/accounts/authorize?client_id=dynamic_agent_client&state=e2e-state'
const CALLBACK_URL = 'http://127.0.0.1:7592/auth/callback'

interface OAuthMocks {
    connectBodies: unknown[]
    completeBodies: unknown[]
}

async function mockChatGPTOAuth(
    page: Page,
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
            await route.fulfill({ status: 200, json: { link: AUTHORIZE_URL } })
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
            if (route.request().method() !== 'GET' || !completed) {
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

    await page.context().route('https://auth.openai.com/**', (route) =>
        route.fulfill({
            status: 200,
            contentType: 'text/html',
            body: '<html><body>Sign in with ChatGPT</body></html>',
        }),
    )

    return mocks
}

async function continueWithChatGPT(page: Page) {
    await page.getByRole('button', { name: 'Integrations' }).click()
    await page.getByRole('tab', { name: 'Providers' }).click()

    const card = page.getByTestId(`integration-card-${INTEGRATION_ID}`)
    await expect(page.getByTestId('ai-family-OPENAI')).toBeVisible()
    await card.getByText('ChatGPT plan', { exact: true }).click()
    await expect(card.getByText('Disabled', { exact: true })).toBeVisible()

    const popupPromise = page.context().waitForEvent('page')
    await card.getByRole('button', { name: 'Continue with ChatGPT' }).click()
    const popup = await popupPromise
    await expect(popup).toHaveURL(AUTHORIZE_URL)
    await popup.close()

    await expect(
        card.getByText('Waiting for authorization in your browser...'),
    ).toBeVisible()
    return card
}

async function pasteCallback(page: Page, query: string) {
    const card = page.getByTestId(`integration-card-${INTEGRATION_ID}`)
    await card
        .getByPlaceholder('http://127.0.0.1:…/auth/callback?code=…')
        .fill(`${CALLBACK_URL}?${query}`)
    await card.getByRole('button', { name: 'Finish' }).click()
}

test.describe('ChatGPT integration', () => {
    test('signs in with ChatGPT and finishes from the pasted address', async ({
        authenticatedPage: page,
    }) => {
        const mocks = await mockChatGPTOAuth(page, { status: 204 })

        const card = await continueWithChatGPT(page)
        await pasteCallback(
            page,
            'code=e2e-code&scope=openid&state=e2e-state&client_id=oaiapp_e2e',
        )

        await expect(
            page.getByText('ChatGPT integration enabled successfully'),
        ).toBeVisible({ timeout: 20_000 })
        await expect(card.getByText('Enabled', { exact: true })).toBeVisible()
        await expect(card.getByText('Using your ChatGPT plan')).toBeVisible()
        await expect(
            card.getByRole('button', { name: 'Manage usage' }),
        ).toBeVisible()

        const appUrl = new URL(page.url())
        expect(mocks.connectBodies).toEqual([
            {
                payload: {},
                completion_url: `${appUrl.origin}${appUrl.pathname}?integration_oauth=${INTEGRATION_ID}${RETURN_ROUTE}`,
            },
        ])
        expect(mocks.completeBodies).toEqual([
            {
                state: 'e2e-state',
                code: 'e2e-code',
                error: null,
                client_id: 'oaiapp_e2e',
            },
        ])
    })

    test('shows an error when the plan permission is declined', async ({
        authenticatedPage: page,
    }) => {
        const mocks = await mockChatGPTOAuth(page, {
            status: 400,
            body: { code: 'AUTHORIZATION_DENIED' },
        })

        const card = await continueWithChatGPT(page)
        await pasteCallback(page, 'error=access_denied&state=e2e-state')

        await expect(
            page.getByText(
                'Access to ChatGPT was denied or the required permissions were not granted.',
            ),
        ).toBeVisible({ timeout: 20_000 })
        expect(mocks.completeBodies).toEqual([
            { state: 'e2e-state', code: null, error: 'access_denied' },
        ])
        await expect(card.getByText('Disabled', { exact: true })).toBeVisible()
        await expect(
            card.getByRole('button', { name: 'Continue with ChatGPT' }),
        ).toBeVisible()
    })
})
