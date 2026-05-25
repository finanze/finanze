import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { TEST_PASSWORD } from '../../helpers/constants'

const logout = async (page: import('@playwright/test').Page) => {
    await page.locator('button[aria-label="Logout"]').click()
    await page.locator('button.text-red-500', { hasText: 'Logout' }).waitFor()
    await page.locator('button.text-red-500', { hasText: 'Logout' }).click()
    await page.locator('#password').waitFor({ timeout: 10_000 })
}

test.describe('Login Retry and Edge Cases', () => {
    test('wrong password then correct password succeeds', async ({
        authenticatedPage: page,
    }) => {
        await logout(page)

        await page.fill('#password', 'WrongPassword!')
        await page.locator('button[type="submit"]').click()
        await expect(page.getByText('Invalid credentials')).toBeVisible({
            timeout: 5_000,
        })

        await page.fill('#password', TEST_PASSWORD)
        await page.locator('button[type="submit"]').click()

        await expect(page).not.toHaveURL(/login/, { timeout: 20_000 })
        await expect(
            page.getByRole('heading', { name: 'Summary' }),
        ).toBeVisible({ timeout: 10_000 })
    })

    test('multiple wrong attempts then correct password succeeds', async ({
        authenticatedPage: page,
    }) => {
        await logout(page)

        for (let i = 0; i < 3; i++) {
            await page.fill('#password', `WrongPass${i}!`)
            await page.locator('button[type="submit"]').click()
            await expect(page.getByText('Invalid credentials')).toBeVisible({
                timeout: 5_000,
            })
        }

        await page.fill('#password', TEST_PASSWORD)
        await page.locator('button[type="submit"]').click()

        await expect(page).not.toHaveURL(/login/, { timeout: 20_000 })
        await expect(
            page.getByRole('heading', { name: 'Summary' }),
        ).toBeVisible({ timeout: 10_000 })
    })

    test('welcome back message shows username after logout', async ({
        authenticatedPage: page,
    }) => {
        await logout(page)

        await expect(
            page.getByRole('heading', { name: /Welcome back/ }),
        ).toBeVisible({ timeout: 5_000 })
    })

    test('returning user sees only password field, not username', async ({
        authenticatedPage: page,
    }) => {
        await logout(page)

        await expect(page.locator('#password')).toBeVisible()
        await expect(page.locator('#username')).not.toBeVisible()
    })
})
