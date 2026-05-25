import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { TEST_PASSWORD, TEST_NEW_PASSWORD } from '../../helpers/constants'

const openChangePassword = async (page: import('@playwright/test').Page) => {
    await page.locator('button[aria-label="Logout"]').click()
    await page.getByRole('button', { name: 'Change encryption key' }).waitFor()
    await page.getByRole('button', { name: 'Change encryption key' }).click()
    await page.locator('#oldPassword').waitFor({ timeout: 10_000 })
}

test.describe('Change Encryption Key - Error Cases', () => {
    test('wrong current key shows invalid credentials error', async ({
        authenticatedPage: page,
    }) => {
        await openChangePassword(page)

        await page.fill('#oldPassword', 'WrongPassword!')
        await page.fill('#password', TEST_NEW_PASSWORD)
        await page.fill('#repeatPassword', TEST_NEW_PASSWORD)
        await page.locator('button[type="submit"]').click()

        await expect(page.getByText('Invalid credentials')).toBeVisible({
            timeout: 5_000,
        })
        await expect(page.locator('#oldPassword')).toBeVisible()
    })

    test('mismatched new keys shows error', async ({
        authenticatedPage: page,
    }) => {
        await openChangePassword(page)

        await page.fill('#oldPassword', TEST_PASSWORD)
        await page.fill('#password', 'NewPassword1!')
        await page.fill('#repeatPassword', 'NewPassword2!')
        await page.locator('button[type="submit"]').click()

        await expect(page.getByText("Encryption keys don't match")).toBeVisible(
            { timeout: 5_000 },
        )
    })

    test('invalid new key format shows error', async ({
        authenticatedPage: page,
    }) => {
        await openChangePassword(page)

        await page.fill('#oldPassword', TEST_PASSWORD)
        await page.fill('#password', 'short')
        await page.fill('#repeatPassword', 'short')
        await page.locator('button[type="submit"]').click()

        await expect(
            page.getByText('Encryption key must be at least 8 characters'),
        ).toBeVisible({ timeout: 5_000 })
    })

    test('cancel change key returns to login page', async ({
        authenticatedPage: page,
    }) => {
        await openChangePassword(page)

        await page.locator('button[aria-label="Cancel"]').click()

        // Cancelling exits change-password mode but user is already logged out
        // so we land on the normal login page
        await expect(page.locator('#password')).toBeVisible({ timeout: 10_000 })
        await expect(page.locator('#oldPassword')).not.toBeVisible()
        await expect(
            page.getByRole('heading', { name: /Welcome back/ }),
        ).toBeVisible()
    })

    test('wrong current key then retry with correct key succeeds', async ({
        authenticatedPage: page,
    }) => {
        await openChangePassword(page)

        // First attempt with wrong current key
        await page.fill('#oldPassword', 'WrongPassword!')
        await page.fill('#password', TEST_NEW_PASSWORD)
        await page.fill('#repeatPassword', TEST_NEW_PASSWORD)
        await page.locator('button[type="submit"]').click()

        await expect(page.getByText('Invalid credentials')).toBeVisible({
            timeout: 5_000,
        })

        // Retry with correct current key
        await page.fill('#oldPassword', TEST_PASSWORD)
        await page.fill('#password', TEST_NEW_PASSWORD)
        await page.fill('#repeatPassword', TEST_NEW_PASSWORD)
        await page.locator('button[type="submit"]').click()

        // After success, login page appears
        await expect(page.locator('#oldPassword')).not.toBeVisible({
            timeout: 10_000,
        })
        await page.locator('#password').waitFor({ timeout: 10_000 })

        // Login with new password
        await page.fill('#password', TEST_NEW_PASSWORD)
        await page.locator('button[type="submit"]').click()

        await expect(page).not.toHaveURL(/login/, { timeout: 20_000 })
        await expect(
            page.getByRole('heading', { name: 'Summary' }),
        ).toBeVisible({ timeout: 10_000 })

        // Restore original key
        await openChangePassword(page)
        await page.fill('#oldPassword', TEST_NEW_PASSWORD)
        await page.fill('#password', TEST_PASSWORD)
        await page.fill('#repeatPassword', TEST_PASSWORD)
        await page.locator('button[type="submit"]').click()

        await expect(page.locator('#oldPassword')).not.toBeVisible({
            timeout: 10_000,
        })
    })
})
