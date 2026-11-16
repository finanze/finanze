import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { BACKEND_URL, TEST_PASSWORD } from '../../helpers/constants'
import { sessionHeaders } from '../../helpers/session'

test.describe('API session', () => {
    test('another tab must log in before accessing data', async ({
        authenticatedPage: page,
    }) => {
        const other = await page.context().newPage()
        await other.goto('/')

        await other.locator('#password').waitFor({ timeout: 20_000 })
        await expect(other.locator('#repeatPassword')).toHaveCount(0)

        await other.fill('#password', 'WrongPassword!')
        await other.locator('button[type="submit"]').click()
        await expect(other.getByText('Invalid credentials')).toBeVisible({
            timeout: 5_000,
        })

        await other.fill('#password', TEST_PASSWORD)
        await other.locator('button[type="submit"]').click()
        await expect(other).not.toHaveURL(/login/, { timeout: 20_000 })
        await expect(
            other.getByRole('heading', { name: 'Summary' }),
        ).toBeVisible({ timeout: 10_000 })

        const res = await fetch(`${BACKEND_URL}/api/v1/settings`, {
            headers: await sessionHeaders(page),
        })
        expect(res.status).toBe(200)

        await other.close()
    })

    test('remember me keeps the session for new tabs', async ({
        authenticatedPage: page,
    }) => {
        const other = await page.context().newPage()
        await other.goto('/')

        await other.locator('#password').waitFor({ timeout: 20_000 })
        const remember = other.locator('#rememberSession')
        await expect(remember).toHaveAttribute('aria-checked', 'false')
        await remember.click()
        await expect(remember).toHaveAttribute('aria-checked', 'true')

        await other.fill('#password', TEST_PASSWORD)
        await other.locator('button[type="submit"]').click()
        await expect(
            other.getByRole('heading', { name: 'Summary' }),
        ).toBeVisible({ timeout: 20_000 })
        await other.close()

        const reopened = await page.context().newPage()
        await reopened.goto('/')
        await expect(
            reopened.getByRole('heading', { name: 'Summary' }),
        ).toBeVisible({ timeout: 20_000 })
        await expect(reopened.locator('#password')).toHaveCount(0)
        await reopened.close()
    })

    test('requests without a valid session are rejected', async ({
        authenticatedPage: page,
    }) => {
        const anonymous = await fetch(`${BACKEND_URL}/api/v1/settings`)
        expect(anonymous.status).toBe(401)
        expect((await anonymous.json()).code).toBe('NOT_LOGGED')

        const forged = await fetch(`${BACKEND_URL}/api/v1/settings`, {
            headers: { Authorization: 'Bearer forged-token' },
        })
        expect(forged.status).toBe(401)

        const anonymousStatus = await fetch(`${BACKEND_URL}/api/v1/status`)
        expect((await anonymousStatus.json()).status).toBe('LOCKED')

        const headers = await sessionHeaders(page)
        const status = await fetch(`${BACKEND_URL}/api/v1/status`, { headers })
        expect((await status.json()).status).toBe('UNLOCKED')

        const settings = await fetch(`${BACKEND_URL}/api/v1/settings`, {
            headers,
        })
        expect(settings.status).toBe(200)
    })
})
