import {
    HEADING_XPATH,
    clickIn,
    confirmImport,
    dismissShareSheet,
    ensureSignedIn,
    openMoreMenuPage,
    overlay,
    readLatestExport,
    selectTab,
    setInputFile,
    statementFile,
    textFile,
    waitForText,
} from '../helpers/ui.js'

const IMPORT_DIALOG = 'Import data from file'
const PREVIEW_DIALOG = 'Review simulated import'
const EXPORT_DIALOG = 'Export data to file'
const UNSUPPORTED_FILE =
    'The selected file type is not supported. Upload a CSV, TSV, XLS, XLSX, HTML or PDF file.'

const id = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
const entity = `Mobile Bank ${id}`
const income = `Mobile Salary ${id}`
const expense = `Mobile Groceries ${id}`

function localIso(daysAgo: number) {
    const date = new Date(Date.now() - daysAgo * 86_400_000)
    const pad = (value: number) => String(value).padStart(2, '0')
    return (
        `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
        `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
    )
}

async function openFileImportDialog() {
    await selectTab('Import')
    const importButton = $('//button[normalize-space()="Import..."]')
    await importButton.waitForClickable({ timeout: 15_000 })
    await importButton.click()
    const dialog = overlay(IMPORT_DIALOG)
    await dialog.waitForDisplayed({ timeout: 10_000 })
    await clickIn(dialog, 'Transactions')
    await clickIn(dialog, 'Account')
    return dialog
}

async function closeDialog(dialog: ReturnType<typeof overlay>) {
    await clickIn(dialog, 'Cancel')
    await dialog.waitForDisplayed({ reverse: true, timeout: 10_000 })
}

async function importStatement(name: string, movements: number) {
    const dialog = await openFileImportDialog()
    await setInputFile('#file-import-input', statementFile(name))
    await dialog
        .$('.//*[normalize-space(text())="Ready to import"]')
        .waitForDisplayed({ timeout: 90_000 })

    const createEntity = dialog.$('.//button[@title="Create new entity..."]')
    await createEntity.waitForClickable({ timeout: 5_000 })
    await createEntity.click()
    await dialog
        .$('#file-import-entity-input')
        .setValue(`Mobile ${name.replace('.pdf', '')} ${id}`)
    await clickIn(dialog, 'Preview')

    const preview = overlay(PREVIEW_DIALOG)
    await preview.waitForDisplayed({ timeout: 90_000 })
    await preview
        .$(`.//*[contains(normalize-space(), "${movements} transactions")]`)
        .waitForDisplayed({ timeout: 10_000 })
    await confirmImport(preview)
}

describe('File import and export', () => {
    before(async () => {
        await ensureSignedIn()
        await openMoreMenuPage('Export & Import')
    })

    it('rejects files that cannot be read as a table', async () => {
        const dialog = await openFileImportDialog()
        await setInputFile(
            '#file-import-input',
            textFile('notes.bin', 'application/octet-stream', '\u0000\u0001'),
        )

        await waitForText(UNSUPPORTED_FILE, 60_000)
        await closeDialog(dialog)
    })

    it('imports account movements detected from a CSV file', async () => {
        const dialog = await openFileImportDialog()
        await setInputFile(
            '#file-import-input',
            textFile(
                `movements-${id}.csv`,
                'text/csv',
                [
                    'Fecha contable,Concepto,Importe,Divisa',
                    `${localIso(3)},${income},1500.25,EUR`,
                    `${localIso(2)},${expense},-42.10,EUR`,
                ].join('\n'),
            ),
        )
        await dialog
            .$('.//*[normalize-space(text())="Ready to import"]')
            .waitForDisplayed({ timeout: 60_000 })

        const createEntity = dialog.$(
            './/button[@title="Create new entity..."]',
        )
        await createEntity.waitForClickable({ timeout: 5_000 })
        await createEntity.click()
        await dialog.$('#file-import-entity-input').setValue(entity)
        await clickIn(dialog, 'Preview')

        const preview = overlay(PREVIEW_DIALOG)
        await preview.waitForDisplayed({ timeout: 60_000 })
        await preview
            .$('.//*[contains(normalize-space(), "2 transactions")]')
            .waitForDisplayed({ timeout: 10_000 })
        await confirmImport(preview)
    })

    it('imports every movement of a landscape bank statement PDF spanning several pages', async () => {
        await importStatement('b100.pdf', 31)
    })

    it('imports a bank statement PDF drawn on rotated pages', async () => {
        await importStatement('ing.pdf', 34)
    })

    it('requires choosing what to export', async () => {
        await selectTab('Export')
        const exportButton = $('//button[normalize-space()="Export..."]')
        await exportButton.waitForClickable({ timeout: 15_000 })
        await exportButton.click()
        const dialog = overlay(EXPORT_DIALOG)
        await dialog.waitForDisplayed({ timeout: 10_000 })

        await clickIn(dialog, 'Export')
        await waitForText('Select what to export to continue.')
        await closeDialog(dialog)
    })

    it('exports the imported movements to a CSV file on the device', async () => {
        await selectTab('Export')
        const exportButton = $('//button[normalize-space()="Export..."]')
        await exportButton.waitForClickable({ timeout: 15_000 })
        await exportButton.click()
        const dialog = overlay(EXPORT_DIALOG)
        await dialog.waitForDisplayed({ timeout: 10_000 })
        await clickIn(dialog, 'Transactions')
        await clickIn(dialog, 'Account')
        await clickIn(dialog, 'All time')
        await clickIn(dialog, 'Export')

        await dismissShareSheet(90_000)
        await dialog.waitForDisplayed({ reverse: true, timeout: 30_000 })

        const exported = await readLatestExport('.csv')
        expect(exported.name).toMatch(/\.csv$/)
        expect(exported.content).toContain(income)
        expect(exported.content).toContain(expense)
        expect(exported.content).toContain('1500.25')

        await $(HEADING_XPATH('Export & Import')).waitForDisplayed({
            timeout: 10_000,
        })
    })
})
