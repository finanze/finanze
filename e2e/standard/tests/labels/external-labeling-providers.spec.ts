import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { navigateToMyMoneyPage } from '../../helpers/my-money'
import { TEST_PASSWORD } from '../../helpers/constants'
import en from '../../../../frontend/app/src/i18n/locales/en.json' with { type: 'json' }
import es from '../../../../frontend/app/src/i18n/locales/es.json' with { type: 'json' }
import itTranslations from '../../../../frontend/app/src/i18n/locales/it.json' with { type: 'json' }

test.describe('External labeling providers', () => {
    test('labeling follows the default AI models configured in settings', async ({
        authenticatedPage: page,
    }) => {
        await page.setViewportSize({ width: 1440, height: 1000 })
        const navigation = page.getByRole('navigation')
        await navigation
            .getByRole('button', { name: en.common.entities, exact: true })
            .click()
        await page
            .getByRole('tab', { name: en.entities.tabProviders, exact: true })
            .click()
        await expect(page.getByTestId('ai-models-card')).toHaveCount(0)
        await page.getByTestId('ai-models-settings-link').click()
        await expect(
            page.getByRole('tab', { name: en.settings.aiTab.title }),
        ).toHaveAttribute('aria-selected', 'true')
        const models = page.getByTestId('ai-models-card')
        await expect(models).toContainText(en.settings.aiModels.empty)
        await models.getByTestId('ai-models-add-provider').click()
        await page.getByTestId('ai-models-provider-option-OPENAI').click()
        await expect(models.getByTestId('ai-models-priority-0')).toContainText(
            'gpt-6-luna',
        )
        await models.getByTestId('ai-models-save').click()
        await expect(models.getByTestId('ai-models-save')).toBeHidden()

        await navigateToMyMoneyPage(page, 'Activity')
        await page.getByRole('tab', { name: en.labels.tabs.automation }).click()
        const card = page.getByTestId('external-labeling-card')
        await card.getByTestId('external-labeling-switch').click()
        await expect(card.getByTestId('external-priority-0')).toContainText(
            'gpt-6-luna',
        )
        await expect(card.getByTestId('external-editor')).toHaveAttribute(
            'aria-disabled',
            'true',
        )
        await expect(card.getByTestId('external-add-provider')).toHaveCount(0)

        await card.getByTestId('external-custom-toggle').click()
        await expect(card.getByTestId('external-editor')).not.toHaveAttribute(
            'aria-disabled',
            'true',
        )
        await expect(card.getByTestId('external-priority-0')).toContainText(
            'gpt-6-luna',
        )
        await expect(card.getByTestId('external-add-provider')).toBeVisible()
        await card.getByTestId('external-custom-toggle').click()
        await expect(card.getByTestId('external-editor')).toHaveAttribute(
            'aria-disabled',
            'true',
        )

        await card.getByTestId('external-edit-default').click()
        await expect(page.getByTestId('ai-models-card')).toHaveClass(/ring-2/)
        const priority = page.getByTestId('ai-models-priority-0')
        await expect(priority).toContainText('gpt-6-luna')
        await priority.getByRole('button', { name: /Remove/ }).click()
        await models.getByTestId('ai-models-save').click()
        await expect(models.getByTestId('ai-models-save')).toBeHidden()
        await expect(models).toContainText(en.settings.aiModels.empty)
    })

    test('switches integration names across languages without changing priorities or refetching integrations', async ({
        authenticatedPage: page,
    }, testInfo) => {
        let integrationRequests = 0
        let savedProviders: { provider: string; model: string }[] | undefined
        let savedLabeling:
            | { external: { providers: { provider: string; model: string }[] } }
            | undefined
        page.on('request', (request) => {
            const pathname = new URL(request.url()).pathname
            if (
                pathname === '/api/v1/integrations' &&
                request.method() === 'GET'
            )
                integrationRequests += 1
        })
        await page.route(
            (url) => url.pathname === '/api/v1/settings',
            async (route) => {
                const request = route.request()
                if (request.method() === 'POST') {
                    const labeling = request.postDataJSON().labeling
                    if (!labeling) return route.fallback()
                    savedLabeling = labeling
                    savedProviders = labeling.external?.providers
                    return route.fulfill({ status: 204 })
                }
                const response = await route.fetch()
                const body = await response.json()
                if (savedLabeling) body.labeling = savedLabeling
                await route.fulfill({ response, json: body })
            },
        )
        await page.route(
            (url) => url.pathname === '/api/v1/integrations',
            async (route) => {
                const response = await route.fetch()
                const body = await response.json()
                body.integrations = body.integrations.map(
                    (integration: { id: string }) =>
                        integration.id === 'OPENAI_COMPATIBLE'
                            ? { ...integration, status: 'ON', available: true }
                            : integration,
                )
                await route.fulfill({ response, json: body })
            },
        )
        await page.route(
            (url) => url.pathname === '/api/v1/ai/providers',
            (route) =>
                route.fulfill({
                    json: {
                        providers: [
                            {
                                id: 'OPENAI_COMPATIBLE',
                                connected: true,
                                custom_models: false,
                                upstream_providers: false,
                                recommended_models: [
                                    {
                                        id: 'locale-model',
                                        name: 'locale-model',
                                        probabilistic: false,
                                    },
                                ],
                            },
                        ],
                    },
                }),
        )

        await page.setViewportSize({ width: 1440, height: 1000 })
        await navigateToMyMoneyPage(page, 'Activity')
        await page.getByRole('tab', { name: en.labels.tabs.automation }).click()
        const card = page.getByTestId('external-labeling-card')
        await card.getByTestId('external-labeling-switch').click()
        await card.getByTestId('external-custom-toggle').click()
        await card.getByTestId('external-add-provider').click()
        await page
            .getByTestId('external-provider-option-OPENAI_COMPATIBLE')
            .click()
        await expect(card.getByTestId('external-priority-0')).toContainText(
            'locale-model',
        )
        await card
            .getByRole('button', { name: en.common.save, exact: true })
            .click()
        await expect(
            card.getByRole('button', { name: en.common.save, exact: true }),
        ).toBeHidden()
        expect(savedProviders).toMatchObject([
            { provider: 'OPENAI_COMPATIBLE', model: 'locale-model' },
        ])

        let current: typeof en | typeof es | typeof itTranslations = en
        for (const [locale, translations] of [
            ['es-ES', es],
            ['it-IT', itTranslations],
        ] as const) {
            await page
                .getByRole('button', {
                    name: current.common.settings,
                    exact: true,
                })
                .click()
            await page
                .getByRole('tab', {
                    name: current.settings.application,
                    exact: true,
                })
                .click()
            const requestsBeforeLanguageChange = integrationRequests
            await page.locator('#application-language').selectOption(locale)
            await expect(page.locator('#application-language')).toHaveValue(
                locale,
            )
            current = translations

            const navigation = page.getByRole('navigation')
            await navigation
                .getByRole('button', {
                    name: translations.common.entities,
                    exact: true,
                })
                .click()
            await page
                .getByRole('tab', {
                    name: translations.entities.tabProviders,
                    exact: true,
                })
                .click()
            await expect(
                page.getByTestId('integration-card-OPENAI_COMPATIBLE'),
            ).toContainText(
                translations.settings.integration.OPENAI_COMPATIBLE.name,
            )
            await expect(
                page.getByTestId('integration-card-LOCAL_MODELS'),
            ).toContainText(translations.settings.integration.LOCAL_MODELS.name)
            await expect(
                page.getByTestId('integration-card-CLAUDE_AGENT'),
            ).toContainText(
                translations.settings.aiProviderMethods.CLAUDE_AGENT,
            )

            const myMoney = navigation.getByRole('button', {
                name: translations.management.title,
                exact: true,
            })
            if ((await myMoney.getAttribute('aria-expanded')) !== 'true')
                await myMoney.click()
            await navigation
                .getByRole('button', {
                    name: translations.management.cashflow,
                    exact: true,
                })
                .click()
            await page
                .getByRole('tab', { name: translations.labels.tabs.automation })
                .click()
            await expect(card.getByTestId('external-priority-0')).toContainText(
                `${translations.settings.aiProviderFamilies.CUSTOM} - ${translations.settings.aiProviderMethods.OPENAI_COMPATIBLE}`,
            )
            await expect(card.getByTestId('external-priority-0')).toContainText(
                'locale-model',
            )
            await expect(
                card.getByRole('button', {
                    name: translations.common.save,
                    exact: true,
                }),
            ).toBeHidden()
            expect(integrationRequests).toBe(requestsBeforeLanguageChange)
            expect(savedProviders).toMatchObject([
                { provider: 'OPENAI_COMPATIBLE', model: 'locale-model' },
            ])
            await card.screenshot({
                path: testInfo.outputPath(`localized-priority-${locale}.png`),
            })
        }
        await page.setViewportSize({ width: 390, height: 844 })
        await card.screenshot({
            path: testInfo.outputPath('localized-priority-mobile.png'),
        })
        expect(
            await page.evaluate(
                () => document.documentElement.scrollWidth <= window.innerWidth,
            ),
        ).toBe(true)
    })

    test('preserves priority order across runtime availability changes and reports fallback', async ({
        authenticatedPage: page,
    }, testInfo) => {
        let claudeAvailable = true
        let savedLabeling:
            | {
                  external: {
                      enabled: boolean
                      providers: { provider: string; model: string }[]
                  }
              }
            | undefined
        let externalRequested = false
        const models = [
            { id: 'OPENROUTER', model: 'router-model' },
            { id: 'CLAUDE_AGENT', model: 'claude-model' },
            { id: 'CHATGPT', model: 'chat-model' },
        ]
        await page.route(
            (url) => url.pathname === '/api/v1/integrations',
            async (route) => {
                const response = await route.fetch()
                const body = await response.json()
                body.integrations = body.integrations.map(
                    (integration: { id: string }) =>
                        models.some((item) => item.id === integration.id)
                            ? {
                                  ...integration,
                                  status: 'ON',
                                  available:
                                      integration.id !== 'CLAUDE_AGENT' ||
                                      claudeAvailable,
                              }
                            : integration,
                )
                await route.fulfill({ response, json: body })
            },
        )
        await page.route(
            (url) => url.pathname === '/api/v1/ai/providers',
            (route) =>
                route.fulfill({
                    json: {
                        providers: models
                            .filter(
                                (item) =>
                                    item.id !== 'CLAUDE_AGENT' ||
                                    claudeAvailable,
                            )
                            .map((item) => ({
                                id: item.id,
                                connected: true,
                                custom_models: false,
                                upstream_providers: false,
                                recommended_models: [
                                    {
                                        id: item.model,
                                        name: item.model,
                                        probabilistic: false,
                                    },
                                ],
                            })),
                    },
                }),
        )
        await page.route(
            (url) => url.pathname === '/api/v1/settings',
            async (route) => {
                const request = route.request()
                if (request.method() === 'POST') {
                    const body = request.postDataJSON()
                    if (!body.labeling) return route.fallback()
                    savedLabeling = body.labeling
                    return route.fulfill({ status: 204 })
                }
                const response = await route.fetch()
                const body = await response.json()
                if (savedLabeling) body.labeling = savedLabeling
                await route.fulfill({ response, json: body })
            },
        )
        await page.route(
            (url) => url.pathname === '/api/v1/labeling/relabel',
            (route) => {
                externalRequested = route
                    .request()
                    .postDataJSON().include_external
                const result = {
                    processed: 1,
                    linked: 0,
                    paired: 0,
                    rule_labeled: 0,
                    external_labeled: 0,
                    skipped_locked: 0,
                    skipped_linked: 0,
                }
                return route.fulfill({
                    json: {
                        matched: 1,
                        result,
                        external: {
                            ...result,
                            external_labeled: 1,
                            external_provider: 'CHATGPT',
                            external_model: 'chat-model',
                        },
                    },
                })
            },
        )

        await page.setViewportSize({ width: 1440, height: 1000 })
        await navigateToMyMoneyPage(page, 'Activity')
        await page.getByRole('tab', { name: /Automation/ }).click()
        const card = page.getByTestId('external-labeling-card')
        await card.getByTestId('external-labeling-switch').click()
        await card.getByTestId('external-custom-toggle').click()
        const add = card.getByTestId('external-add-provider')
        await add.click()
        await page.getByTestId('external-provider-option-OPENROUTER').click()
        await expect(card.getByTestId('external-priority-0')).toContainText(
            'router-model',
        )
        await add.click()
        await page.getByTestId('external-provider-option-CLAUDE_AGENT').click()
        await expect(card.getByTestId('external-priority-1')).toContainText(
            'claude-model',
        )
        await add.click()
        await page.getByTestId('external-provider-option-CHATGPT').click()
        await expect(card.getByTestId('external-priority-2')).toContainText(
            'chat-model',
        )
        await expect(card.getByText('3/5', { exact: true })).toBeVisible()
        await card
            .getByTestId('external-priority-1')
            .getByRole('button', { name: 'Move up', exact: true })
            .click()
        await card.getByRole('button', { name: 'Save', exact: true }).click()
        await expect(
            card.getByRole('button', { name: 'Save', exact: true }),
        ).toBeHidden()
        expect(
            savedLabeling?.external.providers.map((entry) => entry.provider),
        ).toEqual(['CLAUDE_AGENT', 'OPENROUTER', 'CHATGPT'])

        claudeAvailable = false
        await page.locator('button[aria-label="Logout"]').click()
        await page.locator('button.text-red-500', { hasText: 'Logout' }).click()
        await page.locator('#password').fill(TEST_PASSWORD)
        await page.locator('button[type="submit"]').click()
        await expect(
            page.getByRole('heading', { name: 'Summary' }),
        ).toBeVisible({ timeout: 20_000 })
        await navigateToMyMoneyPage(page, 'Activity')
        await page.getByRole('tab', { name: /Automation/ }).click()
        await expect(card.getByTestId('external-priority-0')).toContainText(
            'Unavailable here',
        )
        await expect(card.getByTestId('external-priority-1')).toContainText(
            'Preferred here',
        )
        await expect(card.getByTestId('external-entry-editor')).toHaveAttribute(
            'disabled',
            '',
        )
        await expect(page.getByTestId('external-priority-notice')).toBeHidden()
        await card.getByTestId('external-priority-info').click()
        const priorityInfo = page.getByRole('dialog', {
            name: en.labels.external.priorityTitle,
        })
        await expect(
            priorityInfo.getByTestId('external-priority-notice'),
        ).toContainText('unavailable on this platform')
        await priorityInfo.screenshot({
            path: testInfo.outputPath('priority-info-desktop.png'),
        })
        await page.keyboard.press('Escape')
        await expect(priorityInfo).toBeHidden()
        await card.screenshot({
            path: testInfo.outputPath('priority-desktop.png'),
        })
        await page.setViewportSize({ width: 390, height: 844 })
        await card.screenshot({
            path: testInfo.outputPath('priority-mobile.png'),
        })
        await card.getByTestId('external-priority-info').click()
        await priorityInfo.screenshot({
            path: testInfo.outputPath('priority-info-mobile.png'),
        })
        await page.keyboard.press('Escape')
        await expect(priorityInfo).toBeHidden()
        expect(
            await page.evaluate(
                () => document.documentElement.scrollWidth <= window.innerWidth,
            ),
        ).toBe(true)

        await page.getByRole('button', { name: 'Relabel', exact: true }).click()
        const dialog = page.getByRole('dialog')
        await expect(
            dialog.getByText('router-model', { exact: true }),
        ).toBeVisible()
        const external = dialog.getByTestId('relabel-external-switch')
        if ((await external.getAttribute('aria-checked')) !== 'true')
            await external.click()
        await dialog
            .getByRole('button', { name: 'Relabel', exact: true })
            .click()
        await expect(dialog.getByTestId('relabel-provider-used')).toContainText(
            'Fallback used: ChatGPT (chat-model)',
        )
        expect(externalRequested).toBe(true)
        expect(savedLabeling?.external.providers[0].provider).toBe(
            'CLAUDE_AGENT',
        )
    })

    test('adds chosen AI providers with icons and concise method names', async ({
        authenticatedPage: page,
    }, testInfo) => {
        await page.setViewportSize({ width: 1440, height: 1000 })
        await navigateToMyMoneyPage(page, 'Activity')
        await page.getByRole('tab', { name: /Automation/ }).click()

        const card = page.getByTestId('external-labeling-card')
        await card.waitFor({ timeout: 10_000 })
        await card.getByTestId('external-labeling-switch').click()
        await card.getByTestId('external-custom-toggle').click()
        const add = card.getByTestId('external-add-provider')
        await add.click()
        await expect(card.getByTestId('external-priority-0')).toBeHidden()
        await expect(card.getByRole('combobox')).toBeHidden()

        const openRouter = page.getByTestId(
            'external-provider-option-OPENROUTER',
        )
        const openAI = page.getByTestId('external-provider-option-OPENAI')
        await expect(openRouter).toBeVisible()
        await expect(openAI).toBeVisible()
        await expect(
            page.getByRole('group', { name: 'OpenAI', exact: true }),
        ).toBeVisible()
        await expect(openAI).toHaveText(en.settings.aiProviderMethods.OPENAI)
        await expect(openRouter).toHaveText(
            en.settings.aiProviderMethods.OPENROUTER,
        )
        await expect(openAI.locator('img')).toHaveAttribute(
            'src',
            'icons/external-integrations/OPENAI.png',
        )
        const picker = page.getByRole('dialog')
        await picker.screenshot({
            path: testInfo.outputPath('provider-picker-desktop.png'),
        })
        await page.setViewportSize({ width: 390, height: 844 })
        await picker.screenshot({
            path: testInfo.outputPath('provider-picker-mobile.png'),
        })
        expect(
            await page.evaluate(
                () => document.documentElement.scrollWidth <= window.innerWidth,
            ),
        ).toBe(true)

        await openAI.click()
        await expect(openAI).toBeHidden()
        const row = card.getByTestId('external-priority-0')
        await expect(row).toContainText('OpenAI')
        await expect(card.getByText('GPT-6 Luna')).toBeVisible()
        await expect(
            card
                .getByTestId('external-entry-editor')
                .getByText('gpt-6-luna', { exact: true }),
        ).toBeVisible()
        await expect(
            card
                .getByTestId('external-entry-editor')
                .getByText('Not connected'),
        ).toBeVisible()

        await add.click()
        await page.getByTestId('external-provider-option-OPENROUTER').click()
        await expect(picker).toBeHidden()
        await expect(row).toContainText('OpenAI')
        await expect(card.getByTestId('external-priority-1')).toContainText(
            'OpenRouter',
        )
        await expect(
            card
                .getByTestId('external-entry-editor')
                .getByText('~typesafe/jev-latest'),
        ).toBeVisible()
        const up = row.getByRole('button', {
            name: en.labels.external.moveUp,
            exact: true,
        })
        const down = row.getByRole('button', {
            name: en.labels.external.moveDown,
            exact: true,
        })
        await expect(up.locator('..')).toHaveCSS('flex-direction', 'column')
        const upBounds = await up.boundingBox()
        const downBounds = await down.boundingBox()
        expect(Math.abs(upBounds!.x - downBounds!.x)).toBeLessThan(1)
        expect(downBounds!.y).toBeGreaterThanOrEqual(
            upBounds!.y + upBounds!.height,
        )
        const rowBounds = await row.boundingBox()
        const removeBounds = await row
            .getByRole('button', { name: /Remove/ })
            .boundingBox()
        expect(
            rowBounds!.x +
                rowBounds!.width -
                removeBounds!.x -
                removeBounds!.width,
        ).toBeGreaterThanOrEqual(8)
        await card.screenshot({
            path: testInfo.outputPath('priority-editor-mobile.png'),
        })
        await page.setViewportSize({ width: 1440, height: 1000 })
        await expect(up.locator('..')).toHaveCSS('flex-direction', 'row')
        await card.screenshot({
            path: testInfo.outputPath('priority-editor-desktop.png'),
        })
        const openAIName = `${en.settings.aiProviderFamilies.OPENAI} - ${en.settings.aiProviderMethods.OPENAI}`
        await row
            .getByRole('button', {
                name: en.labels.external.editProvider.replace(
                    '{provider}',
                    openAIName,
                ),
                exact: true,
            })
            .click()
        await card
            .getByRole('button', {
                name: en.labels.external.connectProvider,
                exact: true,
            })
            .click()
        const focusedMethod = page.getByTestId('integration-card-OPENAI')
        await expect(focusedMethod).toHaveClass(/ring-inset/)
        const highlightStyle = await focusedMethod.evaluate((element) => {
            const style = getComputedStyle(element)
            return {
                radius: parseFloat(style.borderRadius),
                padding: parseFloat(style.paddingLeft),
                inset: style.boxShadow.includes('inset'),
            }
        })
        expect(highlightStyle.radius).toBeGreaterThan(0)
        expect(highlightStyle.padding).toBeGreaterThanOrEqual(12)
        expect(highlightStyle.inset).toBe(true)
        const family = page.getByTestId('ai-family-OPENAI')
        const divider = await focusedMethod.evaluate((element) => {
            const style = getComputedStyle(element, '::after')
            return { height: style.height, radius: style.borderRadius }
        })
        expect(divider.height).toBe('1px')
        expect(divider.radius).toBe('0px')
        const finalDivider = await family
            .getByTestId('integration-card-CHATGPT')
            .evaluate((element) => getComputedStyle(element, '::after').display)
        expect(finalDivider).toBe('none')
        for (const [viewport, label] of [
            [{ width: 1440, height: 1000 }, 'desktop'],
            [{ width: 390, height: 844 }, 'mobile'],
        ] as const) {
            await page.setViewportSize(viewport)
            const alignment = await family
                .getByText(en.settings.aiProviderFamilies.OPENAI, {
                    exact: true,
                })
                .evaluate((title) => {
                    const icon = title
                        .closest('[data-testid="ai-family-OPENAI"]')!
                        .querySelector(
                            '[data-testid="integration-card-OPENAI"] img',
                        )!
                    return Math.abs(
                        title.getBoundingClientRect().x -
                            icon.getBoundingClientRect().x,
                    )
                })
            expect(alignment).toBeLessThan(1)
            await family.screenshot({
                path: testInfo.outputPath(`family-highlight-${label}.png`),
            })
        }
    })
})
