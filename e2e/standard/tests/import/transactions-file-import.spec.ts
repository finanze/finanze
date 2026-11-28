import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect, type Locator, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'

const ACCOUNT_HEADERS = 'ref,name,amount,currency,date,counterparty,iban'
const CRYPTO_HEADERS =
    'ref,name,amount,currency,type,date,symbol,currency_amount,price,fees'
const PORTFOLIO_HEADERS = 'ref,name,amount,currency,type,date,portfolio_name'
const IBAN = 'ES91 2100 0418 4502 0005 1332'
const XLS_FIXTURE = join(
    import.meta.dirname,
    '..',
    '..',
    '..',
    '..',
    'tests',
    'resources',
    'import',
    'bank_movements.xls',
)
const XLS_MIME = 'application/vnd.ms-excel'
const UNSUPPORTED_FILE =
    'The selected file type is not supported. Upload a CSV, TSV, XLS, XLSX, HTML or PDF file.'
const PDF_NO_TEXT_ERROR =
    'This PDF contains scanned images or vector outlines without selectable text. Export the statement as CSV, Excel, or a text-based PDF.'

type ImportProduct = 'Account' | 'Crypto' | 'Fund Portfolio'

interface UploadFile {
    name: string
    mimeType: string
    buffer: Buffer
}

function uid() {
    return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
}

function localIso(daysAgo: number) {
    const date = new Date(Date.now() - daysAgo * 86_400_000)
    const pad = (value: number) => String(value).padStart(2, '0')
    return (
        `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
        `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
    )
}

function localDayMonthYear(daysAgo: number) {
    const date = new Date(Date.now() - daysAgo * 86_400_000)
    const pad = (value: number) => String(value).padStart(2, '0')
    return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`
}

function csv(...rows: string[]) {
    return rows.join('\n')
}

function csvFile(name: string, ...rows: string[]): UploadFile {
    return { name, mimeType: 'text/csv', buffer: Buffer.from(csv(...rows)) }
}

const ES_MONTHS = [
    'ene',
    'feb',
    'mar',
    'abr',
    'may',
    'jun',
    'jul',
    'ago',
    'sep',
    'oct',
    'nov',
    'dic',
]

function localSpanishDateParts(daysAgo: number) {
    const date = new Date(Date.now() - daysAgo * 86_400_000)
    const day = String(date.getDate()).padStart(2, '0')
    return {
        dayMonth: `${day} ${ES_MONTHS[date.getMonth()]}`,
        year: String(date.getFullYear()),
    }
}

function pdfFile(name: string, stream: string): UploadFile {
    const objects = [
        '1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
        '2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
        '3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n',
        '4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>\nendobj\n',
        `5 0 obj\n<< /Length ${Buffer.byteLength(stream, 'latin1')} >>\nstream\n${stream}\nendstream\nendobj\n`,
    ]
    let pdf = '%PDF-1.4\n'
    const offsets: number[] = [0]
    for (const obj of objects) {
        offsets.push(Buffer.byteLength(pdf, 'latin1'))
        pdf += obj
    }
    const xrefOffset = Buffer.byteLength(pdf, 'latin1')
    pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`
    for (let i = 1; i <= objects.length; i++) {
        pdf += `${String(offsets[i]).padStart(10, '0')} 00000 n \n`
    }
    pdf += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`
    return {
        name,
        mimeType: 'application/pdf',
        buffer: Buffer.from(pdf, 'latin1'),
    }
}

function overlay(page: Page, text: string) {
    return page.locator('.fixed.inset-0').filter({ hasText: text }).last()
}

async function openImportTab(page: Page) {
    await page.getByRole('button', { name: 'Export & Import' }).click()
    await page
        .getByRole('heading', { name: 'Export & Import' })
        .waitFor({ timeout: 10_000 })
    await page.getByRole('tab', { name: 'Import' }).click()
    await expect(page.getByText('Import templates')).toBeVisible({
        timeout: 10_000,
    })
}

async function startImportTemplate(
    page: Page,
    name: string,
    product: ImportProduct,
) {
    await page.getByRole('button', { name: 'Manage', exact: true }).click()
    const manager = overlay(page, 'Template manager')
    await expect(manager).toBeVisible({ timeout: 10_000 })
    await manager.getByRole('button', { name: 'New template' }).click()
    await manager.locator('#template-name').fill(name)
    await manager
        .getByRole('button', { name: 'Transactions', exact: true })
        .click()
    await manager.getByRole('button', { name: product, exact: true }).click()
    await expect(manager.locator('#custom-name-ref')).toBeVisible({
        timeout: 5_000,
    })
    return manager
}

async function saveImportTemplate(page: Page, manager: Locator) {
    await manager.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(page.getByText('Template created.')).toBeVisible({
        timeout: 10_000,
    })
    await manager.locator('button:has(svg.lucide-x)').first().click()
    await expect(manager).toBeHidden({ timeout: 5_000 })
}

async function createImportTemplate(
    page: Page,
    name: string,
    product: ImportProduct,
) {
    const manager = await startImportTemplate(page, name, product)
    await saveImportTemplate(page, manager)
}

async function pickOption(
    dialog: Locator,
    placeholder: string,
    option: string,
) {
    await dialog.getByText(placeholder, { exact: true }).click()
    await dialog.getByPlaceholder('Search options...').fill(option)
    await dialog.getByText(option, { exact: true }).last().click()
}

async function openFileImportDialog(page: Page, product: ImportProduct) {
    await page.getByRole('button', { name: 'Import...' }).click()
    const dialog = overlay(page, 'Import data from file')
    await expect(dialog).toBeVisible({ timeout: 5_000 })
    await dialog
        .getByRole('button', { name: 'Transactions', exact: true })
        .click()
    await dialog.getByRole('button', { name: product, exact: true }).click()
    return dialog
}

async function selectImportEntity(page: Page, dialog: Locator, entity: string) {
    await dialog.locator('#file-import-entity').click()
    await page
        .locator('[data-radix-popper-content-wrapper]')
        .last()
        .getByText(entity, { exact: true })
        .click()
    await expect(dialog.locator('#file-import-entity')).toContainText(entity)
}

async function submitFileImport(
    page: Page,
    options: {
        template: string
        product: ImportProduct
        entity: string
        newEntity: boolean
        content: string | UploadFile
    },
) {
    const dialog = await openFileImportDialog(page, options.product)
    await pickOption(dialog, 'Select a template', options.template)

    if (options.newEntity) {
        await dialog.getByTitle('Create new entity...').click()
        await dialog.locator('#file-import-entity-input').fill(options.entity)
    } else {
        await selectImportEntity(page, dialog, options.entity)
    }

    await dialog
        .locator('#file-import-input')
        .setInputFiles(
            typeof options.content === 'string'
                ? csvFile('movements.csv', options.content)
                : options.content,
        )
    await dialog.getByRole('button', { name: 'Preview', exact: true }).click()
    return dialog
}

async function previewFileImport(
    page: Page,
    options: Parameters<typeof submitFileImport>[1],
) {
    await submitFileImport(page, options)
    const preview = overlay(page, 'Review simulated import')
    await expect(preview).toBeVisible({ timeout: 15_000 })
    return preview
}

async function confirmWarnings(page: Page, expected: string[]) {
    const warnings = overlay(page, 'Import Warnings')
    await expect(warnings).toBeVisible({ timeout: 10_000 })
    for (const text of expected) {
        await expect(warnings.getByText(text).first()).toBeVisible()
    }
    await warnings.getByRole('button', { name: 'Confirm' }).click()
    await expect(warnings).toBeHidden({ timeout: 5_000 })
}

async function confirmImport(preview: Locator) {
    await preview.getByRole('button', { name: 'Import data' }).click()
}

async function expectImportCompleted(page: Page, preview: Locator) {
    await confirmImport(preview)
    await expect(
        page.getByText('File imported successfully. Refreshing your data...'),
    ).toBeVisible({ timeout: 15_000 })
    await expect(preview).toBeHidden({ timeout: 5_000 })
}

async function searchTransactions(page: Page, text: string) {
    await page
        .getByRole('button', { name: 'Transactions', exact: true })
        .first()
        .click()
    await page
        .getByRole('heading', { name: 'Transactions' })
        .first()
        .waitFor({ timeout: 10_000 })
    const search = page.locator('#transaction-search')
    await search.fill(text)
    await search.press('Enter')
}

async function expandTransaction(page: Page, txName: string) {
    const txRow = page
        .getByText(txName, { exact: true })
        .first()
        .locator('../..')
    await txRow.getByTestId('expand-tx').click()
}

test.describe('Transactions file import', () => {
    test('imports account movements with inferred types, IBAN and counterparty', async ({
        authenticatedPage: page,
    }) => {
        const id = uid()
        const template = `E2E Account Import ${id}`
        const entity = `E2E Import Bank ${id}`

        await openImportTab(page)
        await createImportTemplate(page, template, 'Account')

        const preview = await previewFileImport(page, {
            template,
            product: 'Account',
            entity,
            newEntity: true,
            content: csv(
                ACCOUNT_HEADERS,
                `a1,Salary ${id},2500,EUR,${localIso(2)},ACME ${id},${IBAN}`,
                `a2,Rent ${id},-900.50,EUR,${localIso(1)},,`,
            ),
        })
        await expect(preview.getByText('2 transactions')).toBeVisible()
        await expect(preview.getByText(`Salary ${id}`).first()).toBeVisible()

        await confirmImport(preview)
        await expect(
            page.getByText(
                'File imported successfully. Refreshing your data...',
            ),
        ).toBeVisible({ timeout: 15_000 })
        await expect(preview).toBeHidden({ timeout: 5_000 })

        await searchTransactions(page, id)
        await expect(page.getByText(`Rent ${id}`).first()).toBeVisible({
            timeout: 10_000,
        })
        await expect(page.getByText(`Salary ${id}`).first()).toBeVisible()

        await expandTransaction(page, `Salary ${id}`)
        await expect(page.getByTestId('tx-iban').first()).toHaveText(IBAN, {
            timeout: 5_000,
        })
        await expect(page.getByText(`ACME ${id}`).first()).toBeVisible()
    })

    test('skips movements whose reference was already imported', async ({
        authenticatedPage: page,
    }) => {
        const id = uid()
        const template = `E2E Dup Import ${id}`
        const entity = `E2E Dup Bank ${id}`

        await openImportTab(page)
        await createImportTemplate(page, template, 'Account')

        const first = await previewFileImport(page, {
            template,
            product: 'Account',
            entity,
            newEntity: true,
            content: csv(
                ACCOUNT_HEADERS,
                `d1,Coffee ${id},-3.20,EUR,${localIso(3)},,`,
            ),
        })
        await confirmImport(first)
        await expect(
            page.getByText(
                'File imported successfully. Refreshing your data...',
            ),
        ).toBeVisible({ timeout: 15_000 })
        await expect(first).toBeHidden({ timeout: 5_000 })

        const second = await previewFileImport(page, {
            template,
            product: 'Account',
            entity,
            newEntity: false,
            content: csv(
                ACCOUNT_HEADERS,
                `d1,Coffee ${id},-3.20,EUR,${localIso(3)},,`,
                `d2,Lunch ${id},-12,EUR,${localIso(2)},,`,
            ),
        })
        await confirmWarnings(page, [
            'Duplicated Transaction',
            'reference d1 is already used by another transaction of this entity',
        ])
        await expect(second.getByText('1 transactions')).toBeVisible()
        await expect(second.getByText(`Lunch ${id}`).first()).toBeVisible()

        await confirmImport(second)
        await confirmWarnings(page, ['Duplicated Transaction'])
        await expect(second).toBeHidden({ timeout: 5_000 })

        await searchTransactions(page, id)
        await expect(page.getByText(`Lunch ${id}`).first()).toBeVisible({
            timeout: 10_000,
        })
        await expect(
            page
                .getByText(`Coffee ${id}`, { exact: true })
                .filter({ visible: true }),
        ).toHaveCount(1)
    })

    test('reports invalid rows and imports only the valid ones', async ({
        authenticatedPage: page,
    }) => {
        const id = uid()
        const template = `E2E Invalid Import ${id}`
        const entity = `E2E Invalid Bank ${id}`

        await openImportTab(page)
        await createImportTemplate(page, template, 'Account')

        const preview = await previewFileImport(page, {
            template,
            product: 'Account',
            entity,
            newEntity: true,
            content: csv(
                ACCOUNT_HEADERS,
                `v1,Valid ${id},10,EUR,${localIso(1)},,`,
                `v2,Bad IBAN ${id},10,EUR,${localIso(1)},,ES#1`,
                `v3,,10,EUR,${localIso(1)},,`,
                `v4,Bad amount ${id},ten,EUR,${localIso(1)},,`,
            ),
        })
        await confirmWarnings(page, [
            'Validation Error',
            'Field iban: invalid value ES#1',
            'Missing Field',
        ])
        await expect(preview.getByText('1 transactions')).toBeVisible()

        await confirmImport(preview)
        await confirmWarnings(page, [
            'Your data was imported successfully, but some rows were skipped',
        ])
        await expect(preview).toBeHidden({ timeout: 5_000 })

        await searchTransactions(page, id)
        await expect(page.getByText(`Valid ${id}`).first()).toBeVisible({
            timeout: 10_000,
        })
        await expect(page.getByText(`Bad IBAN ${id}`)).toHaveCount(0)
        await expect(page.getByText(`Bad amount ${id}`)).toHaveCount(0)
    })

    test('imports crypto trades', async ({ authenticatedPage: page }) => {
        const id = uid()
        const template = `E2E Crypto Import ${id}`
        const entity = `E2E Crypto Venue ${id}`

        await openImportTab(page)
        await createImportTemplate(page, template, 'Crypto')

        const preview = await previewFileImport(page, {
            template,
            product: 'Crypto',
            entity,
            newEntity: true,
            content: csv(
                CRYPTO_HEADERS,
                `c1,Bitcoin buy ${id},500,EUR,BUY,${localIso(2)},btc,0.005,100000,1.5`,
                `c2,Bitcoin sell ${id},-300,EUR,SELL,${localIso(1)},BTC,-0.003,100000,`,
            ),
        })
        await expect(preview.getByText('2 transactions')).toBeVisible()

        await confirmImport(preview)
        await expect(
            page.getByText(
                'File imported successfully. Refreshing your data...',
            ),
        ).toBeVisible({ timeout: 15_000 })

        await searchTransactions(page, id)
        await expect(page.getByText(`Bitcoin buy ${id}`).first()).toBeVisible({
            timeout: 10_000,
        })
        await expect(page.getByText(`Bitcoin sell ${id}`).first()).toBeVisible()
    })

    test('imports fund portfolio fees and rejects unsupported types', async ({
        authenticatedPage: page,
    }) => {
        const id = uid()
        const template = `E2E Portfolio Import ${id}`
        const entity = `E2E Robo ${id}`

        await openImportTab(page)
        await createImportTemplate(page, template, 'Fund Portfolio')

        const preview = await previewFileImport(page, {
            template,
            product: 'Fund Portfolio',
            entity,
            newEntity: true,
            content: csv(
                PORTFOLIO_HEADERS,
                `p1,Custody fee ${id},-12.5,EUR,FEE,${localIso(1)},Main`,
                `p2,Contribution ${id},100,EUR,BUY,${localIso(1)},Main`,
            ),
        })
        await confirmWarnings(page, [
            'Validation Error',
            'Field type: invalid value BUY',
        ])
        await expect(preview.getByText('1 transactions')).toBeVisible()

        await confirmImport(preview)
        await confirmWarnings(page, ['Validation Error'])

        await searchTransactions(page, id)
        await expect(page.getByText(`Custody fee ${id}`).first()).toBeVisible({
            timeout: 10_000,
        })
        await expect(page.getByText(`Contribution ${id}`)).toHaveCount(0)
    })
})

test.describe('Bank file import with detected templates', () => {
    test('detects columns and local formats from a bank CSV export', async ({
        authenticatedPage: page,
    }) => {
        const id = uid()
        const template = `E2E Bank CSV ${id}`
        const entity = `E2E Bank CSV Entity ${id}`
        const file = csvFile(
            'bank.csv',
            'Movimientos de la cuenta;;;',
            `Cuenta;${IBAN};;`,
            ';;;',
            'Fecha operación;Concepto;Importe;Saldo',
            `${localDayMonthYear(2)};Nómina ${id};1.500,00;2.500,00`,
            `${localDayMonthYear(1)};Supermercado ${id};-45,30;2.454,70`,
        )

        await openImportTab(page)
        const manager = await startImportTemplate(page, template, 'Account')
        await manager.locator('#template-detect-file-input').setInputFiles(file)

        await expect(
            manager.getByText('3 columns matched from bank.csv.'),
        ).toBeVisible({ timeout: 10_000 })
        await expect(
            manager.getByText('Columns not mapped: Saldo'),
        ).toBeVisible()
        await expect(manager.locator('#custom-name-date')).toHaveValue(
            'Fecha operación',
        )
        await expect(manager.locator('#custom-name-name')).toHaveValue(
            'Concepto',
        )
        await expect(manager.locator('#custom-name-amount')).toHaveValue(
            'Importe',
        )
        const missingCurrency = manager.getByText(
            'Required fields without a column: Currency.',
        )
        await expect(missingCurrency).toBeVisible()
        await manager.locator('#default-value-currency').selectOption('EUR')
        await expect(missingCurrency).toBeHidden()
        await saveImportTemplate(page, manager)

        const preview = await previewFileImport(page, {
            template,
            product: 'Account',
            entity,
            newEntity: true,
            content: file,
        })
        await expect(preview.getByText('2 transactions')).toBeVisible()
        await expect(preview.getByText(/1,545\.30/).first()).toBeVisible()
        await expect(preview.getByText('Saldo', { exact: true })).toBeVisible()

        await expectImportCompleted(page, preview)

        await searchTransactions(page, id)
        await expect(page.getByText(`Nómina ${id}`).first()).toBeVisible({
            timeout: 10_000,
        })
        await expect(page.getByText(`Supermercado ${id}`).first()).toBeVisible()
    })

    test('imports a legacy XLS bank export', async ({
        authenticatedPage: page,
    }) => {
        const id = uid()
        const template = `E2E Bank XLS ${id}`
        const entity = `E2E Bank XLS Entity ${id}`
        const file: UploadFile = {
            name: 'bank_movements.xls',
            mimeType: XLS_MIME,
            buffer: readFileSync(XLS_FIXTURE),
        }

        await openImportTab(page)
        const manager = await startImportTemplate(page, template, 'Account')
        await manager.locator('#template-detect-file-input').setInputFiles(file)
        await expect(
            manager.getByText('4 columns matched from bank_movements.xls.'),
        ).toBeVisible({ timeout: 10_000 })
        await expect(manager.locator('#custom-name-currency')).toHaveValue(
            'Divisa',
        )
        await expect(
            manager.getByText('Required fields without a column'),
        ).toHaveCount(0)
        await saveImportTemplate(page, manager)

        const preview = await previewFileImport(page, {
            template,
            product: 'Account',
            entity,
            newEntity: true,
            content: file,
        })
        await expect(preview.getByText('3 transactions')).toBeVisible()
        await expect(preview.getByText(/1,605\.55/).first()).toBeVisible()

        await expectImportCompleted(page, preview)

        await searchTransactions(page, 'Recibo luz')
        await expect(page.getByText('Recibo luz').first()).toBeVisible({
            timeout: 10_000,
        })
    })

    test('rejects files that are not spreadsheets', async ({
        authenticatedPage: page,
    }) => {
        const id = uid()
        const template = `E2E Bank Invalid ${id}`
        const file: UploadFile = {
            name: 'movements.xls',
            mimeType: XLS_MIME,
            buffer: Buffer.from('%PDF-1.4 not a spreadsheet'),
        }

        await openImportTab(page)
        const manager = await startImportTemplate(page, template, 'Account')
        await manager.locator('#template-detect-file-input').setInputFiles(file)
        await expect(manager.getByText(UNSUPPORTED_FILE)).toBeVisible({
            timeout: 10_000,
        })
        await expect(manager.getByText(/columns matched from/)).toHaveCount(0)
        await expect(manager.locator('#custom-name-date')).toHaveValue('')
        await saveImportTemplate(page, manager)

        const dialog = await submitFileImport(page, {
            template,
            product: 'Account',
            entity: `E2E Bank Invalid Entity ${id}`,
            newEntity: true,
            content: file,
        })
        await expect(dialog.getByText(UNSUPPORTED_FILE)).toBeVisible({
            timeout: 10_000,
        })
        await expect(overlay(page, 'Review simulated import')).toHaveCount(0)
    })

    test('creates a template from the import dialog and reuses it for the next file', async ({
        authenticatedPage: page,
    }) => {
        const id = uid()
        const template = `bank-${id}`
        const entity = `E2E Detected Bank ${id}`
        const headers = `Fecha contable;Descripción ${id};Importe;Divisa;Saldo`
        const first = csvFile(
            `${template}.csv`,
            headers,
            `${localDayMonthYear(3)};Nómina ${id};1.500,00;EUR;2.500,00`,
            `${localDayMonthYear(2)};Supermercado ${id};-45,30;EUR;2.454,70`,
        )
        const second = csvFile(
            `${template}-next.csv`,
            headers,
            `${localDayMonthYear(1)};Farmacia ${id};-12,40;EUR;2.442,30`,
        )

        await openImportTab(page)
        const dialog = await openFileImportDialog(page, 'Account')
        await dialog.locator('#file-import-input').setInputFiles(first)
        await expect(
            dialog.getByText('Ready to import', { exact: true }),
        ).toBeVisible({ timeout: 10_000 })
        await expect(
            dialog.getByText('4 of 5 columns recognized automatically.'),
        ).toBeVisible()
        await expect(dialog.getByText(/Decimals: 1\.000,00/)).toBeVisible()
        await dialog
            .getByRole('button', { name: 'Create template from file' })
            .click()

        const manager = overlay(page, 'Template manager')
        await expect(manager).toBeVisible({ timeout: 10_000 })
        await expect(manager.locator('#template-name')).toHaveValue(template)
        await expect(
            manager.getByText(`4 columns matched from ${template}.csv.`),
        ).toBeVisible({ timeout: 10_000 })
        await expect(manager.locator('#custom-name-name')).toHaveValue(
            `Descripción ${id}`,
        )
        await expect(manager.locator('#custom-name-currency')).toHaveValue(
            'Divisa',
        )
        await manager.getByRole('button', { name: 'Save', exact: true }).click()
        await expect(page.getByText('Template created.')).toBeVisible({
            timeout: 10_000,
        })
        await expect(manager).toBeHidden({ timeout: 5_000 })
        await expect(
            dialog.getByText(`Matches template “${template}”.`),
        ).toBeVisible({ timeout: 10_000 })

        await dialog.getByTitle('Create new entity...').click()
        await dialog.locator('#file-import-entity-input').fill(entity)
        await dialog
            .getByRole('button', { name: 'Preview', exact: true })
            .click()
        const preview = overlay(page, 'Review simulated import')
        await expect(preview).toBeVisible({ timeout: 15_000 })
        await expect(preview.getByText('2 transactions')).toBeVisible()
        await expectImportCompleted(page, preview)

        const next = await openFileImportDialog(page, 'Account')
        await next.locator('#file-import-input').setInputFiles(second)
        await expect(
            next.getByText(`Matches template “${template}”.`),
        ).toBeVisible({ timeout: 10_000 })
        await selectImportEntity(page, next, entity)
        await next.getByRole('button', { name: 'Preview', exact: true }).click()
        const nextPreview = overlay(page, 'Review simulated import')
        await expect(nextPreview).toBeVisible({ timeout: 15_000 })
        await expect(nextPreview.getByText('1 transactions')).toBeVisible()
        await expectImportCompleted(page, nextPreview)

        await searchTransactions(page, id)
        await expect(page.getByText(`Farmacia ${id}`).first()).toBeVisible({
            timeout: 10_000,
        })
        await expect(page.getByText(`Nómina ${id}`).first()).toBeVisible()
    })

    test('imports a statement directly without selecting a template and resolves fallback currency', async ({
        authenticatedPage: page,
    }) => {
        const id = uid()
        const entity = `E2E Direct Auto Bank ${id}`
        const file = csvFile(
            `direct-${id}.csv`,
            `Fecha contable;Detalle ${id};Importe;Saldo`,
            `${localDayMonthYear(2)};Salario directo ${id};1.850,00;3.100,00`,
            `${localDayMonthYear(1)};Panadería ${id};-6,75;3.093,25`,
        )

        await openImportTab(page)
        await page.locator('#file-import-card-input').setInputFiles(file)
        const dialog = overlay(page, 'Import data from file')
        await expect(dialog).toBeVisible({ timeout: 5_000 })
        await expect(dialog.getByText(`direct-${id}.csv`)).toBeVisible()
        await dialog
            .getByRole('button', { name: 'Transactions', exact: true })
            .click()
        await dialog
            .getByRole('button', { name: 'Account', exact: true })
            .click()
        await expect(
            dialog.getByText('Ready to import', { exact: true }),
        ).toBeVisible({ timeout: 10_000 })
        await expect(
            dialog.getByText('3 of 4 columns recognized automatically.'),
        ).toBeVisible()
        await expect(dialog.locator('#file-import-currency')).toBeVisible()
        await dialog.locator('#file-import-currency').selectOption('EUR')

        await dialog
            .getByRole('button', { name: 'Preview', exact: true })
            .click()
        await expect(
            dialog.getByText('Select an entity to continue.'),
        ).toBeVisible()

        await dialog.getByTitle('Create new entity...').click()
        await dialog.locator('#file-import-entity-input').fill(entity)
        await dialog
            .getByRole('button', { name: 'Preview', exact: true })
            .click()

        const preview = overlay(page, 'Review simulated import')
        await expect(preview).toBeVisible({ timeout: 15_000 })
        await expect(preview.getByText('2 transactions')).toBeVisible()
        await expectImportCompleted(page, preview)

        await searchTransactions(page, id)
        await expect(
            page.getByText(`Salario directo ${id}`).first(),
        ).toBeVisible({ timeout: 10_000 })
        await expect(page.getByText(`Panadería ${id}`).first()).toBeVisible()
    })

    test('imports HTML and PDF bank tables directly and rejects scanned PDFs without selectable text', async ({
        authenticatedPage: page,
    }) => {
        const id = uid()
        const entity = `E2E HTML PDF Bank ${id}`
        const scannedPdf = pdfFile(
            'scanned.pdf',
            'q 10 10 100 20 re S 20 20 m 80 20 l 80 40 20 40 20 20 c S Q',
        )
        const d1 = localSpanishDateParts(2)
        const d2 = localSpanishDateParts(1)
        const statementPdf = pdfFile(
            `statement-${id}.pdf`,
            [
                `BT /F1 10 Tf 1 0 0 1 40 740 Tm (CUENTA EUR: ${IBAN}) Tj ET`,
                'BT /F1 9 Tf 1 0 0 1 40 715 Tm (FECHA) Tj ET',
                'BT /F1 9 Tf 1 0 0 1 130 715 Tm (DESCRIPCION) Tj ET',
                'BT /F1 9 Tf 1 0 0 1 320 715 Tm (ENTRADA DE DINERO) Tj ET',
                'BT /F1 9 Tf 1 0 0 1 450 715 Tm (SALIDA DE DINERO) Tj ET',
                `BT /F1 9 Tf 1 0 0 1 40 694 Tm (${d1.dayMonth}) Tj ET`,
                `BT /F1 9 Tf 1 0 0 1 130 690 Tm (Abono PDF ${id}) Tj ET`,
                'BT /F1 9 Tf 1 0 0 1 320 690 Tm (950,00 EUR) Tj ET',
                `BT /F1 9 Tf 1 0 0 1 40 686 Tm (${d1.year}) Tj ET`,
                `BT /F1 9 Tf 1 0 0 1 40 664 Tm (${d2.dayMonth}) Tj ET`,
                `BT /F1 9 Tf 1 0 0 1 130 660 Tm (Cargo PDF ${id}) Tj ET`,
                'BT /F1 9 Tf 1 0 0 1 450 660 Tm (24,50 EUR) Tj ET',
                `BT /F1 9 Tf 1 0 0 1 40 656 Tm (${d2.year}) Tj ET`,
            ].join('\n'),
        )
        const statementHtml: UploadFile = {
            name: `statement-${id}.html`,
            mimeType: 'text/html',
            buffer: Buffer.from(
                `<!doctype html><html><body><table>
                <tr><th rowspan="2">Fecha</th><th rowspan="2">Concepto</th><th colspan="2">Importe</th></tr>
                <tr><th>Abono</th><th>Cargo</th></tr>
                <tr><td>${localDayMonthYear(2)}</td><td>Ingreso HTML ${id}</td><td>320,00 EUR</td><td></td></tr>
                <tr><td>${localDayMonthYear(1)}</td><td>Gasto HTML ${id}</td><td></td><td>18,90 EUR</td></tr>
                </table></body></html>`,
                'utf-8',
            ),
        }

        await openImportTab(page)
        const dialog = await openFileImportDialog(page, 'Account')
        await dialog.locator('#file-import-input').setInputFiles(scannedPdf)
        await expect(dialog.getByText(PDF_NO_TEXT_ERROR)).toBeVisible({
            timeout: 10_000,
        })

        await dialog.locator('#file-import-input').setInputFiles(statementPdf)
        await expect(
            dialog.getByText('Ready to import', { exact: true }),
        ).toBeVisible({ timeout: 10_000 })
        await expect(dialog.getByText('Detected from file')).toBeVisible()
        await expect(dialog.locator('#file-import-currency')).toHaveValue('EUR')

        await dialog.getByTitle('Create new entity...').click()
        await dialog.locator('#file-import-entity-input').fill(entity)
        await dialog
            .getByRole('button', { name: 'Preview', exact: true })
            .click()
        const pdfPreview = overlay(page, 'Review simulated import')
        await expect(pdfPreview).toBeVisible({ timeout: 15_000 })
        await expect(pdfPreview.getByText('2 transactions')).toBeVisible()
        await expectImportCompleted(page, pdfPreview)

        const htmlDialog = await openFileImportDialog(page, 'Account')
        await htmlDialog
            .locator('#file-import-input')
            .setInputFiles(statementHtml)
        await expect(
            htmlDialog.getByText('Ready to import', { exact: true }),
        ).toBeVisible({ timeout: 10_000 })
        await selectImportEntity(page, htmlDialog, entity)
        await htmlDialog
            .getByRole('button', { name: 'Preview', exact: true })
            .click()
        const htmlPreview = overlay(page, 'Review simulated import')
        await expect(htmlPreview).toBeVisible({ timeout: 15_000 })
        await expect(htmlPreview.getByText('2 transactions')).toBeVisible()
        await expectImportCompleted(page, htmlPreview)

        await searchTransactions(page, id)
        await expect(page.getByText(`Abono PDF ${id}`).first()).toBeVisible({
            timeout: 10_000,
        })
        await expect(page.getByText(`Cargo PDF ${id}`).first()).toBeVisible()
        await expect(page.getByText(`Ingreso HTML ${id}`).first()).toBeVisible()
        await expect(page.getByText(`Gasto HTML ${id}`).first()).toBeVisible()
    })
})

test.describe('Transactions file export', () => {
    test('exports account movements with default 6-month range, format badges, and validation', async ({
        authenticatedPage: page,
    }) => {
        const id = uid()
        const entity = `E2E Export Bank ${id}`
        const recentDateDmy = localDayMonthYear(5)
        const file = csvFile(
            `export-seed-${id}.csv`,
            `Fecha contable,Descripción ${id},Importe,Divisa`,
            `${localIso(5)},Recent Export ${id},1234.56,EUR`,
            `${localIso(240)},Older Export ${id},-89.15,EUR`,
        )

        await openImportTab(page)
        await page.locator('#file-import-card-input').setInputFiles(file)
        const importDialog = overlay(page, 'Import data from file')
        await expect(importDialog).toBeVisible({ timeout: 5_000 })
        await importDialog
            .getByRole('button', { name: 'Transactions', exact: true })
            .click()
        await importDialog
            .getByRole('button', { name: 'Account', exact: true })
            .click()
        await expect(
            importDialog.getByText('Ready to import', { exact: true }),
        ).toBeVisible({ timeout: 10_000 })
        await importDialog.getByTitle('Create new entity...').click()
        await importDialog.locator('#file-import-entity-input').fill(entity)
        await importDialog
            .getByRole('button', { name: 'Preview', exact: true })
            .click()
        const preview = overlay(page, 'Review simulated import')
        await expect(preview).toBeVisible({ timeout: 15_000 })
        await expectImportCompleted(page, preview)

        await page.getByRole('tab', { name: 'Export' }).click()
        await expect(page.getByText('Quick export')).toBeVisible({
            timeout: 10_000,
        })

        await page.getByRole('button', { name: 'Export...' }).click()
        const emptyExportDialog = overlay(page, 'Export data to file')
        await expect(emptyExportDialog).toBeVisible({ timeout: 5_000 })
        await emptyExportDialog
            .getByRole('button', { name: 'Export', exact: true })
            .click()
        await expect(
            emptyExportDialog.getByText('Select what to export to continue.'),
        ).toBeVisible()
        await emptyExportDialog
            .getByRole('button', { name: 'Transactions', exact: true })
            .click()
        await emptyExportDialog
            .getByRole('button', { name: 'Export', exact: true })
            .click()
        await expect(
            emptyExportDialog.getByText('Data is required.'),
        ).toBeVisible()
        await emptyExportDialog
            .getByRole('button', { name: 'Cancel', exact: true })
            .click()
        await expect(emptyExportDialog).toBeHidden({ timeout: 5_000 })

        await page
            .getByRole('button', { name: 'Account movements', exact: true })
            .click()
        const quickDialog = overlay(page, 'Export data to file')
        await expect(quickDialog).toBeVisible({ timeout: 5_000 })
        await expect(
            quickDialog.getByRole('button', {
                name: 'Last 6 months',
                exact: true,
            }),
        ).toHaveAttribute('aria-pressed', 'true')
        await quickDialog
            .getByRole('button', { name: '1.000,00', exact: true })
            .click()
        await quickDialog
            .getByRole('button', { name: 'DD/MM/YYYY HH:mm:ss', exact: true })
            .click()

        const recentDownloadPromise = page.waitForEvent('download')
        await quickDialog
            .getByRole('button', { name: 'Export', exact: true })
            .click()
        const recentDownload = await recentDownloadPromise
        const recentPath = await recentDownload.path()
        expect(recentPath).toBeTruthy()
        const recentCsv = readFileSync(recentPath!, 'utf-8')
        expect(recentCsv).toContain(`Recent Export ${id}`)
        expect(recentCsv).toContain('1234,56')
        expect(recentCsv).toContain(recentDateDmy)
        expect(recentCsv).not.toContain(`Older Export ${id}`)
        await expect(quickDialog).toBeHidden({ timeout: 5_000 })

        await page
            .getByRole('button', { name: 'Account movements', exact: true })
            .click()
        const allTimeDialog = overlay(page, 'Export data to file')
        await expect(allTimeDialog).toBeVisible({ timeout: 5_000 })
        await allTimeDialog
            .getByRole('button', { name: 'All time', exact: true })
            .click()
        await allTimeDialog
            .getByRole('button', { name: 'TSV', exact: true })
            .click()

        const allTimeDownloadPromise = page.waitForEvent('download')
        await allTimeDialog
            .getByRole('button', { name: 'Export', exact: true })
            .click()
        const allTimeDownload = await allTimeDownloadPromise
        expect(allTimeDownload.suggestedFilename()).toMatch(/\.tsv$/)
        const allTimePath = await allTimeDownload.path()
        expect(allTimePath).toBeTruthy()
        const allTimeTsv = readFileSync(allTimePath!, 'utf-8')
        expect(allTimeTsv).toContain(`Recent Export ${id}\t1234.56`)
        expect(allTimeTsv).toContain(`Older Export ${id}\t89.15`)
    })
})
