import { expect } from '@playwright/test'
import { test } from '../../fixtures/backend'
import { TEST_USER, TEST_PASSWORD, BACKEND_URL } from '../../helpers/constants'

test.describe('Initial Setup - Signup', () => {
    test('first visit shows signup form when no user exists', async ({
        page,
        backend,
    }) => {
        await page.goto('/')

        await page.locator('#username').waitFor({ timeout: 20_000 })

        await expect(page.locator('#username')).toBeVisible()
        await expect(page.locator('#password')).toBeVisible()
        await expect(page.locator('#repeatPassword')).toBeVisible()
    })

    test('signup with mismatched passwords shows error', async ({
        page,
        backend,
    }) => {
        // Logout in case a previous test left backend unlocked
        await fetch(`${backend.backendUrl}/api/v1/logout`, {
            method: 'POST',
        }).catch(() => {})

        await page.goto('/')
        await page.locator('#username').waitFor({ timeout: 20_000 })

        await page.fill('#username', TEST_USER)
        await page.fill('#password', 'Password1')
        await page.fill('#repeatPassword', 'Password2')
        await page.locator('button[type="submit"]').click()

        await expect(page.getByText("Passwords don't match")).toBeVisible({
            timeout: 5_000,
        })
    })

    test('signup with valid credentials transitions to dashboard', async ({
        page,
        backend,
    }) => {
        // Logout in case a previous test left backend unlocked
        await fetch(`${backend.backendUrl}/api/v1/logout`, {
            method: 'POST',
        }).catch(() => {})

        await page.goto('/')
        await page.locator('#username').waitFor({ timeout: 20_000 })

        await page.fill('#username', TEST_USER)
        await page.fill('#password', TEST_PASSWORD)
        await page.fill('#repeatPassword', TEST_PASSWORD)
        await page.locator('button[type="submit"]').click()

        await expect(page).not.toHaveURL(/login/, { timeout: 20_000 })

        // Dashboard shows "Summary" heading
        await expect(
            page.getByRole('heading', { name: 'Summary' }),
        ).toBeVisible({ timeout: 10_000 })

        // Lock the backend for subsequent tests
        await fetch(`${backend.backendUrl}/api/v1/logout`, { method: 'POST' })
    })
})
