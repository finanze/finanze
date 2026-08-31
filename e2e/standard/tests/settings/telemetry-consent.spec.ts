import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { BACKEND_URL } from '../../helpers/constants'

test.describe('Telemetry consent', () => {
    test('is opt-in, gates session replay and propagates to the backend', async ({
        authenticatedPage: page,
    }) => {
        const collectorRequests: string[] = []
        page.on('request', (request) => {
            if (request.url().includes('betterstack')) {
                collectorRequests.push(request.url())
            }
        })

        await page.locator('button[aria-label="Settings"]').first().click()

        const errorReporting = page.getByTestId('telemetry-error-reporting')
        const sessionReplay = page.getByTestId('telemetry-session-replay')

        await errorReporting.waitFor({ timeout: 10_000 })
        await expect(errorReporting).toHaveAttribute('data-state', 'unchecked')
        await expect(sessionReplay).toHaveAttribute('data-state', 'unchecked')
        await expect(sessionReplay).toBeDisabled()
        expect(collectorRequests).toHaveLength(0)

        await errorReporting.click()
        await expect(errorReporting).toHaveAttribute('data-state', 'checked')
        await expect(sessionReplay).toBeEnabled()

        const consent = await page.evaluate(async (url) => {
            const res = await fetch(`${url}/api/v1/telemetry/consent`)
            return res.json()
        }, BACKEND_URL)

        expect(consent.errorReporting).toBe(true)
        expect(consent.sessionReplay).toBe(false)

        await errorReporting.click()
        await expect(errorReporting).toHaveAttribute('data-state', 'unchecked')
        await expect(sessionReplay).toBeDisabled()
    })
})
