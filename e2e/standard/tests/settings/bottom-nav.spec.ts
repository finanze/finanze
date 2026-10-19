import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true })

async function expandBar(page: Page) {
    const bar = page.getByTestId('floating-bottom-nav')
    await expect(bar).toBeVisible()
    if ((await bar.getAttribute('data-state')) === 'collapsed') {
        await bar.locator(':scope > div').click()
    }
    await expect(bar).toHaveAttribute('data-state', 'expanded')
    await expect(
        bar.getByRole('button', { name: 'More', exact: true }),
    ).toBeVisible()
    return bar
}

async function openSettings(page: Page) {
    const bar = await expandBar(page)
    const settings = bar.getByRole('button', { name: 'Settings', exact: true })
    if (await settings.isVisible()) {
        await settings.click()
    } else {
        await bar.getByRole('button', { name: 'More', exact: true }).click()
        await page
            .getByRole('button', { name: 'Settings', exact: true })
            .click()
    }
    await page.getByRole('tab', { name: 'Application', exact: true }).click()
    return page.getByTestId('bottom-nav-settings')
}

test('customizes the mobile bar, saves locally, and leaves desktop pins alone', async ({
    authenticatedPage: page,
}, testInfo) => {
    test.setTimeout(120_000)
    const pins = await page.evaluate(() =>
        localStorage.getItem('finanze-pinned-assets'),
    )
    const card = await openSettings(page)
    const inBar = card.getByRole('region', { name: 'In the bar', exact: true })
    const inMenu = card.getByRole('region', {
        name: 'In the More menu',
        exact: true,
    })

    await expect(card.getByRole('status')).toHaveText('6/6')
    await expect(
        card.getByRole('button', { name: 'Move Settings to bar', exact: true }),
    ).toBeDisabled()
    await card
        .getByRole('button', { name: 'Move Calculations to menu', exact: true })
        .click()
    await expect(
        inMenu.getByTestId('bottom-nav-row-calculations'),
    ).toBeVisible()
    await card
        .getByRole('button', { name: 'Add shortcut', exact: true })
        .click()
    await card
        .getByRole('button', {
            name: 'Add Stocks & ETFs shortcut',
            exact: true,
        })
        .click()
    await expect(inBar.getByTestId('bottom-nav-row-stocks-etfs')).toBeVisible()
    await expect(card.getByRole('status')).toHaveText('6/6')

    const handle = card.getByRole('button', {
        name: 'Reorder Summary',
        exact: true,
    })
    await handle.scrollIntoViewIfNeeded()
    const start = await handle.boundingBox()
    const target = await card
        .getByRole('button', { name: 'Reorder Investments', exact: true })
        .boundingBox()
    expect(start).not.toBeNull()
    expect(target).not.toBeNull()
    const session = await page.context().newCDPSession(page)
    const touchX = start!.x + start!.width / 2
    const touchY = start!.y + start!.height / 2
    const destinationY = target!.y + target!.height * 0.8
    await session.send('Input.dispatchTouchEvent', {
        type: 'touchStart',
        touchPoints: [{ x: touchX, y: touchY }],
    })
    for (let step = 1; step <= 15; step++) {
        await session.send('Input.dispatchTouchEvent', {
            type: 'touchMove',
            touchPoints: [
                {
                    x: touchX,
                    y: touchY + ((destinationY - touchY) * step) / 15,
                },
            ],
        })
    }
    await session.send('Input.dispatchTouchEvent', {
        type: 'touchEnd',
        touchPoints: [],
    })
    await session.detach()
    await expect(inBar.getByRole('listitem').first()).toContainText(
        'Investments',
    )

    await card
        .getByRole('button', { name: 'Move Integrations to menu', exact: true })
        .click()
    await card
        .getByRole('button', { name: 'Move My Money to menu', exact: true })
        .click()
    await expect(card.getByRole('status')).toHaveText('4/6')
    for (const button of await inBar
        .getByRole('button', { name: /^Move / })
        .all()) {
        await expect(button).toBeDisabled()
    }

    for (const width of [320, 390]) {
        await page.setViewportSize({ width, height: 844 })
        await card
            .getByRole('heading', { name: 'Bottom bar', exact: true })
            .scrollIntoViewIfNeeded()
        await expandBar(page)
        expect(
            await page.evaluate(
                () => document.documentElement.scrollWidth <= window.innerWidth,
            ),
        ).toBe(true)
        await page.screenshot({
            path: testInfo.outputPath(`bottom-nav-${width}.png`),
        })
    }

    await card
        .getByRole('button', { name: 'Move Settings to bar', exact: true })
        .click()
    const bar = await expandBar(page)
    await bar
        .getByRole('button', { name: 'Stocks & ETFs', exact: true })
        .click()
    await expect(page).toHaveURL(/investments\/stocks-etfs/)
    await expect(
        (await expandBar(page)).getByRole('button', {
            name: 'Stocks & ETFs',
            exact: true,
        }),
    ).toHaveAttribute('aria-current', 'page')

    await openSettings(page)
    await expect(card.getByRole('status')).toHaveText('5/6')
    await expect(inBar.getByRole('listitem').first()).toContainText(
        'Investments',
    )
    const saved = await page.evaluate(() =>
        JSON.parse(localStorage.getItem('finanze-bottom-nav')!),
    )
    expect(saved.bar).toEqual([
        'investments',
        'dashboard',
        'transactions',
        'stocks-etfs',
        'settings',
    ])
    expect(
        await page.evaluate(() =>
            localStorage.getItem('finanze-pinned-assets'),
        ),
    ).toBe(pins)

    await page.setViewportSize({ width: 1280, height: 900 })
    await expect(card).toBeHidden()
    await page.setViewportSize({ width: 390, height: 844 })
    await card
        .getByRole('button', { name: 'Reset to default', exact: true })
        .click()
    await expect(card.getByRole('status')).toHaveText('6/6')
    await expect(card.getByTestId('bottom-nav-row-stocks-etfs')).toBeHidden()
    await expect(
        (await expandBar(page)).getByRole('button', {
            name: 'Calculations',
            exact: true,
        }),
    ).toBeVisible()
})
