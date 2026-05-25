import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import {
    TEST_USER,
    TEST_PASSWORD,
    TEST_NEW_PASSWORD,
} from '../../helpers/constants'

const logout = async (page: import('@playwright/test').Page) => {
    await page.locator('button[aria-label="Logout"]').click()
    await page.locator('button.text-red-500', { hasText: 'Logout' }).waitFor()
    await page.locator('button.text-red-500', { hasText: 'Logout' }).click()
    await page.locator('#password').waitFor({ timeout: 10_000 })
}

const openChangePassword = async (page: import('@playwright/test').Page) => {
    await page.locator('button[aria-label="Logout"]').click()
    await page.getByRole('button', { name: 'Change encryption key' }).waitFor()
    await page.getByRole('button', { name: 'Change encryption key' }).click()
    await page.locator('#oldPassword').waitFor({ timeout: 10_000 })
}

test.describe('Auth Flow Combinations', () => {
    test('login → change key with wrong current → cancel → can login normally', async ({
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

        await page.locator('button[aria-label="Cancel"]').click()

        await expect(page.locator('#password')).toBeVisible({ timeout: 10_000 })
        await expect(page.locator('#oldPassword')).not.toBeVisible()

        await page.fill('#password', TEST_PASSWORD)
        await page.locator('button[type="submit"]').click()

        await expect(
            page.getByRole('heading', { name: 'Summary' }),
        ).toBeVisible({ timeout: 10_000 })
    })

    test('logout → wrong password → correct → change key → login new key → restore original', async ({
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
        await expect(
            page.getByRole('heading', { name: 'Summary' }),
        ).toBeVisible({ timeout: 10_000 })

        await openChangePassword(page)
        await page.fill('#oldPassword', TEST_PASSWORD)
        await page.fill('#password', TEST_NEW_PASSWORD)
        await page.fill('#repeatPassword', TEST_NEW_PASSWORD)
        await page.locator('button[type="submit"]').click()

        await expect(page.locator('#oldPassword')).not.toBeVisible({
            timeout: 10_000,
        })
        await page.locator('#password').waitFor({ timeout: 10_000 })
        await page.fill('#password', TEST_NEW_PASSWORD)
        await page.locator('button[type="submit"]').click()

        await expect(
            page.getByRole('heading', { name: 'Summary' }),
        ).toBeVisible({ timeout: 10_000 })

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
