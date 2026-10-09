import { expect } from '@playwright/test'
import { test as authenticatedTest } from '../fixtures/auth'

type RecentTransactionsRequestCounter = { count: number }

const test = authenticatedTest.extend<{
    recentTransactionsRequestCounter: RecentTransactionsRequestCounter
}>({
    recentTransactionsRequestCounter: async ({}, use) => {
        await use({ count: 0 })
    },
    page: async ({ context, recentTransactionsRequestCounter }, use) => {
        const page = await context.newPage()
        await page.setViewportSize({ width: 390, height: 844 })
        await page.route('**/api/v1/positions*', async (route) => {
            if (route.request().method() !== 'GET') {
                await route.continue()
                return
            }

            await route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify({
                    positions: {
                        'dashboard-e2e': [
                            {
                                id: 'dashboard-e2e',
                                entity: {
                                    id: 'dashboard-e2e',
                                    name: 'Dashboard e2e account',
                                    origin: 'MANUAL',
                                },
                                date: '2026-10-09',
                                source: 'MANUAL',
                                products: {
                                    ACCOUNT: {
                                        entries: [
                                            {
                                                id: 'dashboard-e2e-account',
                                                name: 'Checking account',
                                                total: 1000,
                                                currency: 'EUR',
                                                type: 'CHECKING',
                                                source: 'MANUAL',
                                            },
                                        ],
                                    },
                                },
                            },
                        ],
                    },
                }),
            })
        })
        page.on('request', (request) => {
            const url = new URL(request.url())
            if (
                url.pathname.endsWith('/transactions') &&
                url.searchParams.get('limit') === '8'
            ) {
                recentTransactionsRequestCounter.count += 1
            }
        })
        await use(page)
    },
})

test('loads recent transactions when scrolled into view on mobile', async ({
    authenticatedPage: page,
    recentTransactionsRequestCounter,
}) => {
    await expect(page.getByRole('heading', { name: 'Summary' })).toBeVisible()
    expect(recentTransactionsRequestCounter.count).toBe(0)

    const recentTransactionsHeading = page.getByRole('heading', {
        name: 'Recent Transactions',
    })
    await expect(recentTransactionsHeading).toBeVisible()
    await recentTransactionsHeading.scrollIntoViewIfNeeded()
    await expect.poll(() => recentTransactionsRequestCounter.count).toBe(1)
})
