import { TEST_PASSWORD, TEST_USER } from '../helpers/constants.js'
import {
    installMobileCloudMocks,
    startMobileCloudBackupMockServer,
    type MobileCloudBackupMockServer,
} from '../helpers/cloud-backup-mock-server.js'
import {
    HEADING_XPATH,
    TEXT_XPATH,
    blurActiveElement,
    clickIn,
    confirmImport,
    openMoreMenuPage,
    overlay,
    selectTab,
    setInputFile,
    setInputValue,
    submitLoginForm,
    textFile,
    waitForText,
} from '../helpers/ui.js'
import { switchToWebView } from '../helpers/webview.js'

const CLOUD_EMAIL = 'mobile-cloud@finanze.test'
const CLOUD_PASS = 'CloudPass123!'
const IMPORT_DIALOG = 'Import data from file'
const PREVIEW_DIALOG = 'Review simulated import'

const id = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
const baselineEntity = `Cloud Base Bank ${id}`
const baselineMovement = `Mobile Cloud Base ${id}`
const postBackupEntity = `Cloud Local Bank ${id}`
const postBackupMovement = `Mobile Post Backup ${id}`

function localIso(daysAgo: number): string {
    const date = new Date(Date.now() - daysAgo * 86_400_000)
    const pad = (value: number) => String(value).padStart(2, '0')
    return (
        `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
        `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
    )
}

async function expandBottomNav(): Promise<void> {
    const collapsed = $(
        '[data-testid="floating-bottom-nav"][data-state="collapsed"] > div',
    )
    if (await collapsed.isDisplayed().catch(() => false)) {
        await collapsed.click()
    }
}

async function signInWithCloudMocks(serverPort: number): Promise<void> {
    await switchToWebView()
    const password = $('#password')
    await password.waitForDisplayed({ timeout: 90_000 })
    await installMobileCloudMocks(serverPort, CLOUD_EMAIL)

    if (await $('#username').isDisplayed()) {
        await setInputValue('#username', TEST_USER)
        await setInputValue('#password', TEST_PASSWORD)
        await setInputValue('#repeatPassword', TEST_PASSWORD)
    } else {
        await setInputValue('#password', TEST_PASSWORD)
    }

    await submitLoginForm(5_000)
    await browser.waitUntil(
        async () => !(await browser.getUrl()).includes('/login'),
        { timeout: 60_000, timeoutMsg: 'Still on /login after signing in' },
    )
    await $(HEADING_XPATH('Summary')).waitForDisplayed({ timeout: 30_000 })
}

async function openSettingsTab(tabName: string): Promise<void> {
    await expandBottomNav()
    await openMoreMenuPage('Settings')
    await selectTab(tabName)
}

async function clickButtonByText(
    label: string,
    timeout = 20_000,
): Promise<void> {
    await blurActiveElement()
    const button = $(`//button[normalize-space()="${label}"]`)
    await button.waitForDisplayed({ timeout })
    await button.scrollIntoView({ block: 'center' })
    await button.waitForEnabled({ timeout })
    await button.waitForClickable({ timeout })

    const element = await button
    await browser.execute((el: HTMLElement) => {
        const win = window as unknown as { __e2eBtnClicked?: boolean }
        win.__e2eBtnClicked = false
        el.addEventListener(
            'click',
            () => {
                win.__e2eBtnClicked = true
            },
            { once: true, capture: true },
        )
    }, element)

    await button.click()

    let clicked = await browser.execute(() =>
        Boolean(
            (window as unknown as { __e2eBtnClicked?: boolean })
                .__e2eBtnClicked,
        ),
    )
    if (!clicked) {
        await browser.pause(150)
        clicked = await browser.execute(() =>
            Boolean(
                (window as unknown as { __e2eBtnClicked?: boolean })
                    .__e2eBtnClicked,
            ),
        )
    }
    if (!clicked) {
        await browser.execute((el: HTMLElement) => {
            const btn = el as HTMLButtonElement
            if (!btn.disabled) {
                btn.click()
            }
        }, element)
    }
}

async function importSingleMovementCsv(
    movementName: string,
    entityName: string,
): Promise<void> {
    await expandBottomNav()
    await openMoreMenuPage('Export & Import')
    await selectTab('Import')

    await clickButtonByText('Import...', 15_000)
    const dialog = overlay(IMPORT_DIALOG)
    await dialog.waitForDisplayed({ timeout: 10_000 })
    await clickIn(dialog, 'Transactions')
    await clickIn(dialog, 'Account')

    await setInputFile(
        '#file-import-input',
        textFile(
            `cloud-${movementName.replace(/\s+/g, '-')}.csv`,
            'text/csv',
            [
                'Fecha contable,Concepto,Importe,Divisa',
                `${localIso(1)},${movementName},-19.99,EUR`,
            ].join('\n'),
        ),
    )

    await dialog
        .$('.//*[normalize-space(text())="Ready to import"]')
        .waitForDisplayed({ timeout: 60_000 })

    const createEntity = dialog.$('.//button[@title="Create new entity..."]')
    await createEntity.waitForClickable({ timeout: 5_000 })
    await createEntity.click()
    await dialog.$('#file-import-entity-input').setValue(entityName)
    await clickIn(dialog, 'Preview')

    const preview = overlay(PREVIEW_DIALOG)
    await preview.waitForDisplayed({ timeout: 60_000 })
    await confirmImport(preview)
}

async function assertTransactionsState(params: {
    present: string[]
    absent?: string[]
}): Promise<void> {
    await expandBottomNav()
    const txNav = $('button[aria-label="Transactions"]')
    await txNav.waitForClickable({ timeout: 10_000 })
    await txNav.click()
    await $(HEADING_XPATH('Transactions')).waitForDisplayed({ timeout: 20_000 })

    for (const expected of params.present) {
        await browser.waitUntil(
            async () => {
                const matches = await $$(TEXT_XPATH(expected))
                for (const match of matches) {
                    if (await match.isDisplayed()) return true
                }
                return false
            },
            {
                timeout: 20_000,
                timeoutMsg: `Expected transaction "${expected}" to be displayed`,
            },
        )
    }
    for (const unexpected of params.absent ?? []) {
        await browser.waitUntil(
            async () => {
                const matches = await $$(TEXT_XPATH(unexpected))
                for (const match of matches) {
                    if (await match.isDisplayed()) return false
                }
                return true
            },
            {
                timeout: 10_000,
                timeoutMsg: `Expected transaction "${unexpected}" to be absent`,
            },
        )
    }
}

async function backdateCloudPreferences(): Promise<void> {
    const twentyMinutesAgoIso = new Date(Date.now() - 20 * 60_000).toISOString()

    await browser.execute((backdatedIso: string) => {
        const win = window as unknown as {
            __e2ePrefsOpDone?: boolean
            Capacitor?: {
                Plugins?: {
                    Preferences?: {
                        keys: () => Promise<{ keys: string[] }>
                        get: (opts: {
                            key: string
                        }) => Promise<{ value: string | null }>
                        set: (opts: {
                            key: string
                            value: string
                        }) => Promise<void>
                    }
                }
            }
        }
        win.__e2ePrefsOpDone = false
        const prefs = win.Capacitor?.Plugins?.Preferences
        if (!prefs) {
            win.__e2ePrefsOpDone = true
            return
        }

        prefs
            .keys()
            .then(async ({ keys }) => {
                for (const key of keys) {
                    if (!key.startsWith('cloud:')) continue
                    const { value } = await prefs.get({ key })
                    if (!value) continue
                    const parsed = JSON.parse(value) as {
                        backup?: {
                            backups?: { DATA?: { date?: string } }
                        }
                    }
                    if (parsed.backup?.backups?.DATA) {
                        parsed.backup.backups.DATA.date = backdatedIso
                        await prefs.set({
                            key,
                            value: JSON.stringify(parsed),
                        })
                    }
                }
                win.__e2ePrefsOpDone = true
            })
            .catch(() => {
                win.__e2ePrefsOpDone = true
            })
    }, twentyMinutesAgoIso)

    await browser.waitUntil(
        () =>
            browser.execute(
                () =>
                    (window as unknown as { __e2ePrefsOpDone?: boolean })
                        .__e2ePrefsOpDone === true,
            ),
        {
            timeout: 15_000,
            timeoutMsg: 'Timed out backdating cloud preferences',
        },
    )
}

async function logoutAndBackdateLocalRegistry(): Promise<void> {
    await openSettingsTab('General')
    await clickButtonByText('Logout', 15_000)

    await $('#password').waitForDisplayed({ timeout: 30_000 })
    await backdateCloudPreferences()

    await setInputValue('#password', TEST_PASSWORD)
    await submitLoginForm(5_000)
    await $(HEADING_XPATH('Summary')).waitForDisplayed({ timeout: 30_000 })
}

async function resetToFreshOnboarding(mockServerPort: number): Promise<void> {
    await browser.reloadSession()
    await switchToWebView()
    await installMobileCloudMocks(mockServerPort)

    const restoreTrigger = $(
        '//button[normalize-space()="Have a Cloud account? Restore your data"]',
    )
    await restoreTrigger.waitForDisplayed({ timeout: 60_000 })
}

async function submitRestoreAndWaitDownload(
    mockServer: MobileCloudBackupMockServer,
    password: string,
): Promise<void> {
    await setInputValue('#encryptionKey', password, 30_000)
    const prevDownloads = mockServer.getDownloadCount()
    await clickButtonByText('Restore', 15_000)
    await browser.waitUntil(
        () => mockServer.getDownloadCount() > prevDownloads,
        {
            timeout: 60_000,
            timeoutMsg: 'Expected mobile client to download backup piece',
        },
    )
}

describe('Cloud backup and Point 3 DB protection', () => {
    let mockServer: MobileCloudBackupMockServer

    before(async () => {
        mockServer = await startMobileCloudBackupMockServer()
        await signInWithCloudMocks(mockServer.port)
    })

    after(async () => {
        await mockServer?.close()
    })

    it('protects logged-in mobile DB with ROLLBACK_DATA on failed imports, restores valid backups, and overrides OUTDATED_APP', async () => {
        await importSingleMovementCsv(baselineMovement, baselineEntity)

        await openSettingsTab('Cloud')
        await setInputValue('input[type="email"]', CLOUD_EMAIL, 20_000)
        await setInputValue('input[type="password"]', CLOUD_PASS, 10_000)
        await clickButtonByText('Sign in with Email', 15_000)
        await waitForText(CLOUD_EMAIL, 20_000)

        await clickButtonByText('Manual', 15_000)
        await clickButtonByText('Sync now', 20_000)
        await waitForText('Synced', 60_000)

        const originalBackup = mockServer.getDataPiece()
        expect(originalBackup).not.toBeNull()
        expect(originalBackup!.version).toBeGreaterThanOrEqual(120005)

        const tenMinutesAgoIso = new Date(
            Date.now() - 10 * 60_000,
        ).toISOString()
        const agedValidBackup = mockServer.createBackdatedBackupPiece({
            piece: originalBackup!,
            password: TEST_PASSWORD,
            date: tenMinutesAgoIso,
        })

        await logoutAndBackdateLocalRegistry()
        await importSingleMovementCsv(postBackupMovement, postBackupEntity)

        await mockServer.mutateDataPiece({
            basePayload: originalBackup!.payload,
            password: TEST_PASSWORD,
            mode: 'ahead_of_time',
        })
        await openSettingsTab('Cloud')
        await clickButtonByText('Sync now', 20_000)
        await waitForText('Conflict detected', 20_000)
        await clickButtonByText('Use remote', 15_000)
        await waitForText(
            'Backup was created with a newer version of Finanze. Please update the app.',
            60_000,
        )
        await assertTransactionsState({
            present: [baselineMovement, postBackupMovement],
        })

        await mockServer.mutateDataPiece({
            basePayload: originalBackup!.payload,
            password: TEST_PASSWORD,
            mode: 'mid_upgrade_failure',
        })
        await openSettingsTab('Cloud')
        await waitForText('Conflict detected', 20_000)
        await clickButtonByText('Use remote', 15_000)
        await waitForText('Unexpected error occurred', 60_000)
        await assertTransactionsState({
            present: [baselineMovement, postBackupMovement],
        })

        await mockServer.restoreDataPieceAsNewer(agedValidBackup, {
            date: tenMinutesAgoIso,
        })
        await openSettingsTab('Cloud')
        await waitForText('Conflict detected', 20_000)
        await clickButtonByText('Use remote', 15_000)
        await waitForText('Synced', 60_000)
        await assertTransactionsState({
            present: [baselineMovement],
            absent: [postBackupMovement],
        })

        const futureVersionPiece = await mockServer.restoreDataPieceAsNewer(
            originalBackup!,
            { version: 130001 },
        )
        await openSettingsTab('Cloud')
        await clickButtonByText('Sync now', 20_000)
        await waitForText('Update required', 20_000)
        await waitForText('Newer backup version (v0.13.0)', 15_000)
        const useRemoteBtn = $('//button[normalize-space()="Use remote"]')
        await useRemoteBtn.waitForDisplayed({ timeout: 5_000 })
        expect(await useRemoteBtn.isEnabled()).toBe(false)

        await clickButtonByText('Use local', 15_000)
        await waitForText('Synced', 60_000)

        const overriddenPiece = mockServer.getDataPiece()
        expect(overriddenPiece).not.toBeNull()
        expect(overriddenPiece!.id).not.toBe(futureVersionPiece.id)
        expect(overriddenPiece!.version).toBe(originalBackup!.version)
    })

    it('protects onboarding Restore from Cloud against outdated, wrong-key, and mid-upgrade failing backups, then restores valid backup', async () => {
        const baselinePiece = mockServer.getDataPiece()
        expect(baselinePiece).not.toBeNull()
        const tenMinutesAgoIso = new Date(
            Date.now() - 10 * 60_000,
        ).toISOString()
        const agedValidBackup = mockServer.createBackdatedBackupPiece({
            piece: baselinePiece!,
            password: TEST_PASSWORD,
            date: tenMinutesAgoIso,
        })

        await resetToFreshOnboarding(mockServer.port)

        await mockServer.restoreDataPieceAsNewer(agedValidBackup, {
            version: 130001,
        })
        await clickButtonByText(
            'Have a Cloud account? Restore your data',
            15_000,
        )
        await setInputValue('input[type="email"]', CLOUD_EMAIL, 15_000)
        await setInputValue('input[type="password"]', CLOUD_PASS, 10_000)
        await clickButtonByText('Sign in with Email', 15_000)
        await waitForText(
            'This backup was created with Finanze v0.13.0. Please update the app to restore it.',
            20_000,
        )

        await mockServer.restoreDataPieceAsNewer(agedValidBackup)
        await clickButtonByText('Sign in with Email', 15_000)
        await waitForText('Backup found!', 20_000)

        await setInputValue(
            '#restoreUsername',
            'restored_mobile_user',
            15_000,
        )

        await submitRestoreAndWaitDownload(mockServer, 'WrongKey999!')
        await $('#encryptionKey').waitForDisplayed({ timeout: 60_000 })
        await waitForText(
            'Invalid encryption key. Please check and try again.',
            30_000,
        )

        await mockServer.mutateDataPiece({
            basePayload: agedValidBackup.payload,
            password: TEST_PASSWORD,
            mode: 'ahead_of_time',
        })
        await submitRestoreAndWaitDownload(mockServer, TEST_PASSWORD)
        await $('#encryptionKey').waitForDisplayed({ timeout: 60_000 })
        await waitForText(
            'This backup was created with a newer version of Finanze. Please update the app to restore it.',
            60_000,
        )

        await mockServer.mutateDataPiece({
            basePayload: agedValidBackup.payload,
            password: TEST_PASSWORD,
            mode: 'mid_upgrade_failure',
        })
        await submitRestoreAndWaitDownload(mockServer, TEST_PASSWORD)
        await $('#encryptionKey').waitForDisplayed({ timeout: 60_000 })
        await waitForText('Restore failed. Please try again.', 60_000)

        await mockServer.restoreDataPieceAsNewer(agedValidBackup)
        await submitRestoreAndWaitDownload(mockServer, TEST_PASSWORD)
        await $(HEADING_XPATH('Summary')).waitForDisplayed({ timeout: 60_000 })

        await assertTransactionsState({
            present: [baselineMovement],
            absent: [postBackupMovement],
        })
    })
})
