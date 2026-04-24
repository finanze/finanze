import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { MYINVESTOR_CREDENTIALS } from '../../helpers/constants'

async function goToIntegrations(page: import('@playwright/test').Page) {
    await page.getByRole('button', { name: 'Integrations' }).click()
    await page
        .getByRole('heading', { name: 'Integrations' })
        .waitFor({ timeout: 15_000 })

    const cancelBtn = page.getByRole('button', { name: 'Cancel' })
    if (await cancelBtn.isVisible({ timeout: 1_000 }).catch(() => false)) {
        await cancelBtn.click()
        await page.waitForTimeout(500)
    }
}

async function isEntityConnected(
    page: import('@playwright/test').Page,
    entityName: string,
): Promise<boolean> {
    const card = page
        .locator('h3', { hasText: entityName })
        .first()
        .locator('../..')
    return await card
        .getByRole('button', { name: 'Fetch' })
        .isVisible({ timeout: 2_000 })
        .catch(() => false)
}

async function connectMyInvestorAndReload(
    page: import('@playwright/test').Page,
) {
    await page.getByText('MyInvestor').first().click()
    await page.getByText('Enter credentials for').waitFor({ timeout: 5_000 })
    await page.locator('#user').fill(MYINVESTOR_CREDENTIALS.user)
    await page.locator('#password').fill(MYINVESTOR_CREDENTIALS.password)
    await page.getByRole('button', { name: 'Submit' }).click()

    await expect(page.getByText('Security verification for')).toBeVisible({
        timeout: 10_000,
    })

    await expect(
        page.getByText('Successfully logged in to MyInvestor'),
    ).toBeVisible({ timeout: 15_000 })

    await page.reload()
    await page.waitForLoadState('networkidle')
}

test.describe('Challenge Window - Connect MyInvestor via reCAPTCHA challenge', () => {
    test('connect entity with challenge window auto-completion', async ({
        authenticatedPage: page,
    }) => {
        await goToIntegrations(page)

        if (!(await isEntityConnected(page, 'MyInvestor'))) {
            await page.getByText('MyInvestor').first().click()
            await page
                .getByText('Enter credentials for')
                .waitFor({ timeout: 5_000 })

            await page.locator('#user').fill(MYINVESTOR_CREDENTIALS.user)
            await page
                .locator('#password')
                .fill(MYINVESTOR_CREDENTIALS.password)
            await page.getByRole('button', { name: 'Submit' }).click()

            await expect(
                page.getByText('Security verification for'),
            ).toBeVisible({ timeout: 10_000 })

            await expect(
                page.getByText('Successfully logged in to MyInvestor'),
            ).toBeVisible({ timeout: 15_000 })
        }
    })
})

test.describe('Challenge Window - Shows error when unavailable (web platform)', () => {
    test('challenge window shows incompatible platform error', async ({
        authenticatedPage: page,
    }) => {
        await page.evaluate(() =>
            (window as any).__e2eDisableMockChallengeWindow?.(),
        )

        await goToIntegrations(page)

        const myiCard = page
            .locator('h3', { hasText: 'MyInvestor' })
            .first()
            .locator('../..')
        const reloginBtn = myiCard.getByRole('button', {
            name: 'Relogin',
        })
        const isConnected = await reloginBtn
            .isVisible({ timeout: 2_000 })
            .catch(() => false)

        if (isConnected) {
            await reloginBtn.click()
        } else {
            await page.getByText('MyInvestor').first().click()
        }

        await page
            .getByText('Enter credentials for')
            .waitFor({ timeout: 5_000 })

        await page.locator('#user').fill(MYINVESTOR_CREDENTIALS.user)
        await page.locator('#password').fill(MYINVESTOR_CREDENTIALS.password)
        await page.getByRole('button', { name: 'Submit' }).click()

        await expect(
            page.getByText('Use the app in order to do manual log in.'),
        ).toBeVisible({ timeout: 10_000 })

        await page.evaluate(() =>
            (window as any).__e2eEnableMockChallengeWindow?.(),
        )
    })
})

test.describe('Challenge Window - Fetch data from challenge entity', () => {
    test('fetch data from connected MyInvestor with challenge', async ({
        authenticatedPage: page,
    }) => {
        await goToIntegrations(page)

        if (!(await isEntityConnected(page, 'MyInvestor'))) {
            await connectMyInvestorAndReload(page)
            await goToIntegrations(page)
        }

        const myiFetch = page
            .locator('h3', { hasText: 'MyInvestor' })
            .first()
            .locator('../..')
            .getByRole('button', { name: 'Fetch' })
        await myiFetch.click()

        await expect(
            page.getByText('Select features to fetch from MyInvestor'),
        ).toBeVisible({ timeout: 5_000 })

        await page
            .locator('.fixed')
            .getByRole('button', { name: 'Fetch' })
            .click()

        await expect(
            page.getByText('Data successfully fetched from MyInvestor'),
        ).toBeVisible({ timeout: 30_000 })
    })
})
