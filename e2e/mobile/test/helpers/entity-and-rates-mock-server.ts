import { createServer, type IncomingMessage, type Server } from 'node:http'
import type { AddressInfo } from 'node:net'

export const MOCK_MYINVESTOR_USER = '71739020L'
export const MOCK_MYINVESTOR_PASSWORD = 'ValidPassword123!'
export const MOCK_MYINVESTOR_OTP = '123456'

export const MOCK_CASH_ACCOUNT_NAME = 'MyInvestor Cash E2E'
export const MOCK_FUND_NAME = 'Vanguard Global Stock E2E'
export const MOCK_FUND_ISIN = 'IE00B03HD191'
export const MOCK_STOCK_NAME = 'Apple USD E2E'
export const MOCK_STOCK_ISIN = 'US0378331005'
export const MOCK_STOCK_TICKER = 'AAPL'
export const MOCK_CONTRIBUTION_ALIAS = 'Monthly Vanguard E2E'
export const MOCK_CASH_INFLOW_CONCEPT = 'Payroll Transfer E2E'
export const MOCK_CASH_INTEREST_CONCEPT = 'Monthly Interest E2E'

const SIGNATURE_REQUEST_ID = '2625a7cd-0c61-456c-b1c1-4cf562cc280e'
const SIGNATURE_ID = 'SIG987654'
const CASH_ACCOUNT_ID = '326832'
const SEC_ACCOUNT_ID = 'sec-e2e-001'
const CARD_ID = 'card-e2e-8899'
export const MOCK_METAL_PRICES: Readonly<Record<string, number>> = {
    XAU: 2435.75,
    XAG: 32.48,
    XPT: 945.36,
    XPD: 1028.59,
}

export interface RecordedMockRequest {
    method: string
    path: string
    target: string
    status: number
}

export interface EntityAndRatesMockServer {
    port: number
    requests: RecordedMockRequest[]
    setFailEntityFetch: (fail: boolean) => void
    clearRequests: () => void
    close: () => Promise<void>
}

function isoDateDaysAgo(daysAgo: number): string {
    const d = new Date(Date.now() - daysAgo * 86_400_000)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`
}

function isoDateTimeDaysAgo(daysAgo: number): string {
    return `${isoDateDaysAgo(daysAgo)}T12:00:00.000Z`
}

function readJsonBody(
    request: IncomingMessage,
): Promise<Record<string, unknown>> {
    return new Promise((resolve) => {
        const chunks: Buffer[] = []
        request.on('data', (chunk) => chunks.push(chunk))
        request.on('end', () => {
            try {
                resolve(JSON.parse(Buffer.concat(chunks).toString() || '{}'))
            } catch {
                resolve({})
            }
        })
        request.on('error', () => resolve({}))
    })
}

function buildFxRates(base: 'eur' | 'usd'): Record<string, unknown> {
    const today = isoDateDaysAgo(0)
    const rates: Record<string, number> =
        base === 'eur'
            ? {
                  eur: 1,
                  usd: 1.08,
                  gbp: 0.8425,
                  chf: 0.9355,
                  jpy: 162.85,
                  cad: 1.485,
                  aud: 1.642,
              }
            : {
                  usd: 1,
                  eur: 0.925926,
                  gbp: 0.780093,
                  chf: 0.866204,
                  jpy: 150.787,
                  cad: 1.375,
                  aud: 1.52037,
              }

    for (let i = 0; i < 160; i++) {
        const code = `c${String(i).padStart(2, '0')}`
        rates[code] = Number((0.123456 + i * 0.0731).toFixed(6))
    }

    return {
        date: today,
        [base]: rates,
    }
}

function buildFundOrdersStressList() {
    const completeDate = isoDateDaysAgo(5)
    const pendingDate = isoDateDaysAgo(1)
    const orders: Record<string, unknown>[] = [
        {
            reference: 'fund-ord-complete-1',
            status: 'COMPLETE',
            orderDate: completeDate,
            operationType: 'INVESTMENT_FUNDS_SUBSCRIPTION',
            fundName: ` ${MOCK_FUND_NAME} `,
            currency: 'EUR',
            isin: MOCK_FUND_ISIN,
            market: 'FUND',
            amount: 500.0,
            shares: 4.1494,
            createdEpochMs: 1763477702000,
            maxSafeProbe: Number.MAX_SAFE_INTEGER,
        },
        {
            reference: 'fund-ord-pending-1',
            status: 'PENDING',
            orderDate: pendingDate,
            operationType: 'INVESTMENT_FUNDS_SUBSCRIPTION',
            fundName: MOCK_FUND_NAME,
            currency: 'EUR',
            isin: MOCK_FUND_ISIN,
            market: 'FUND',
            amount: 250.25,
            shares: 0,
            createdEpochMs: 1763477802000,
        },
    ]

    for (let i = 0; i < 220; i++) {
        orders.push({
            reference: `fund-ord-cancel-${i}`,
            status: 'CANCEL',
            orderDate: completeDate,
            operationType: 'INVESTMENT_FUNDS_SUBSCRIPTION',
            fundName: MOCK_FUND_NAME,
            currency: 'EUR',
            isin: MOCK_FUND_ISIN,
            market: 'FUND',
            amount: Number((100.125 + i * 1.375).toFixed(4)),
            feeEstimate: i % 2 === 0 ? 0.0 : -0.0,
            createdEpochMs: 1763477000000 + i * 1000,
            extraMeta: {
                seq: i,
                ratio: 0.000125 * (i + 1),
                note: i % 3 === 0 ? null : 'cancelled',
            },
        })
    }

    return orders
}

function buildStockOrdersStressList() {
    const completeDate = isoDateDaysAgo(6)
    const pendingDate = isoDateDaysAgo(1)
    const orders: Record<string, unknown>[] = [
        {
            id: 'stk-ord-complete-1',
            status: 'COMPLETE',
            orderDate: completeDate,
            operation: 'PURCHASE_VARIABLE_INCOME_CASH',
            toolName: ` ${MOCK_STOCK_NAME} `,
            ticker: MOCK_STOCK_TICKER,
            currency: 'USD',
            marketId: 'NSQ',
            shares: 2.0,
            price: 205.5,
            createdEpochMs: 1763477902000,
            maxSafeProbe: Number.MAX_SAFE_INTEGER,
        },
        {
            id: 'stk-ord-pending-1',
            status: 'PENDING',
            orderDate: pendingDate,
            operation: 'PURCHASE_VARIABLE_INCOME_CASH',
            toolName: MOCK_STOCK_NAME,
            ticker: MOCK_STOCK_TICKER,
            currency: 'USD',
            marketId: 'NSQ',
            shares: 1.0,
            price: 210.25,
            createdEpochMs: 1763477952000,
        },
    ]

    for (let i = 0; i < 220; i++) {
        orders.push({
            id: `stk-ord-cancel-${i}`,
            status: 'CANCEL',
            orderDate: completeDate,
            operation: 'PURCHASE_VARIABLE_INCOME_CASH',
            toolName: MOCK_STOCK_NAME,
            ticker: MOCK_STOCK_TICKER,
            currency: 'USD',
            marketId: 'NSQ',
            shares: Number((1 + (i % 7) * 0.25).toFixed(2)),
            price: Number((180.55 + i * 0.15).toFixed(2)),
            createdEpochMs: 1763476000000 + i * 1000,
            nestedQuote: {
                bid: 180.5,
                ask: 180.6,
                spread: 0.1,
                settlementNull: null,
            },
        })
    }

    return orders
}

export async function startEntityAndRatesMockServer(): Promise<EntityAndRatesMockServer> {
    const requests: RecordedMockRequest[] = []
    let verifiedDeviceId: string | undefined
    let failEntityFetch = false

    const server: Server = createServer(async (request, response) => {
        const sendJson = (
            status: number,
            body: unknown,
            extraHeaders: Record<string, string> = {},
        ) => {
            response.writeHead(status, {
                'Content-Type': 'application/json; charset=utf-8',
                'Set-Cookie':
                    'myi_edge=ok1; Expires=Wed, 21 Oct 2027 07:28:00 GMT; Path=/, myi_sess=ok2; Path=/',
                ...extraHeaders,
            })
            response.end(JSON.stringify(body))
        }

        const parsed = new URL(request.url ?? '/', 'http://127.0.0.1')
        const pathname = parsed.pathname
        response.once('finish', () =>
            requests.push({
                method: request.method ?? 'GET',
                path: pathname + parsed.search,
                target: pathname.split('/')[2] ?? 'unknown',
                status: response.statusCode,
            }),
        )

        if (pathname === '/__mock/features/keys') {
            return sendJson(200, { version: 1, algo: 1, entries: {} })
        }

        if (pathname.startsWith('/__mock/features')) {
            return sendJson(200, { features: {} })
        }

        if (pathname.startsWith('/__mock/fx')) {
            const subPath = pathname.replace('/__mock/fx', '')
            if (subPath.endsWith('/currencies.min.json')) {
                return sendJson(200, {
                    eur: 'Euro',
                    usd: 'US Dollar',
                    gbp: 'British Pound',
                })
            }
            if (subPath.endsWith('/currencies/eur.min.json')) {
                return sendJson(200, buildFxRates('eur'))
            }
            if (subPath.endsWith('/currencies/usd.min.json')) {
                return sendJson(200, buildFxRates('usd'))
            }
            return sendJson(404, { error: 'fx route not found' })
        }

        if (pathname.startsWith('/__mock/metals/')) {
            const symbol =
                /^\/__mock\/metals\/price\/(XAU|XAG|XPT|XPD)\/EUR$/.exec(
                    pathname,
                )?.[1]
            if (symbol) {
                return sendJson(200, { price: MOCK_METAL_PRICES[symbol] })
            }
            return sendJson(404, { error: 'metal price route not found' })
        }

        if (pathname.startsWith('/__mock/ft')) {
            const partial = parsed.searchParams.get('partial') ?? ''
            return sendJson(200, {
                equities:
                    partial.includes('037833') || partial.includes('AAPL')
                        ? [
                              {
                                  symbol: `${MOCK_STOCK_ISIN}:USD:NSQ:${MOCK_STOCK_TICKER}`,
                                  name: MOCK_STOCK_NAME,
                              },
                          ]
                        : [],
            })
        }

        if (pathname.startsWith('/__mock/myinvestor-config')) {
            return sendJson(200, { enabled: false, mode_name: 'none' })
        }

        if (pathname.startsWith('/__mock/myinvestor-api')) {
            const apiPath = pathname.replace('/__mock/myinvestor-api', '')
            const deviceId = request.headers['x-device-id']

            if (
                request.method === 'POST' &&
                apiPath === '/login/api/v2/auth/token'
            ) {
                const body = await readJsonBody(request)
                if (
                    body.customerId !== MOCK_MYINVESTOR_USER ||
                    body.password !== MOCK_MYINVESTOR_PASSWORD
                ) {
                    return sendJson(400, {
                        status: {
                            code: 'INVALID_CREDENTIALS',
                            message: 'Invalid credentials',
                        },
                    })
                }

                if (!verifiedDeviceId || deviceId !== verifiedDeviceId) {
                    return sendJson(202, {
                        payload: {
                            data: {
                                signatureRequestId: SIGNATURE_REQUEST_ID,
                                status: 'PENDING',
                                pendingSignatureMethods: [['OTP_SMS']],
                            },
                        },
                    })
                }

                return sendJson(200, {
                    payload: {
                        data: {
                            accessToken: 'e2e-myinvestor-access-token',
                            refreshToken: 'e2e-myinvestor-refresh-token',
                            refreshExpiresIn: 3600,
                        },
                    },
                })
            }

            if (
                request.method === 'POST' &&
                apiPath ===
                    `/signature/api/v3/public/signature/${SIGNATURE_REQUEST_ID}`
            ) {
                return sendJson(200, {
                    payload: {
                        data: {
                            type: 'OTP',
                            signatureId: SIGNATURE_ID,
                            method: 'OTP_SMS',
                            channel: 'SMS',
                            destination: '******447',
                        },
                    },
                })
            }

            if (
                request.method === 'POST' &&
                apiPath ===
                    `/signature/api/v3/public/signature/${SIGNATURE_REQUEST_ID}/validate/${SIGNATURE_ID}`
            ) {
                const body = await readJsonBody(request)
                if (body.code !== MOCK_MYINVESTOR_OTP) {
                    return sendJson(400, {
                        status: { code: 'INVALID_OTP', message: 'Bad OTP' },
                    })
                }
                if (typeof deviceId !== 'string' || !deviceId) {
                    return sendJson(400, { error: 'Missing x-device-id' })
                }
                verifiedDeviceId = deviceId
                return sendJson(200, {
                    payload: {
                        data: {
                            signatureRequestId: SIGNATURE_REQUEST_ID,
                            operative: 'LOGIN',
                            status: 'COMPLETE',
                            pendingSignatureMethods: [],
                        },
                    },
                })
            }

            if (failEntityFetch) {
                return sendJson(503, {
                    status: {
                        code: 'UPSTREAM_UNAVAILABLE',
                        message: 'Simulated upstream failure',
                    },
                })
            }

            if (apiPath === '/cperf-server/api/v3/customers/self') {
                return sendJson(200, {
                    payload: { data: { customerId: MOCK_MYINVESTOR_USER } },
                })
            }

            if (apiPath === '/cperf-server/api/v2/cash-accounts/self') {
                return sendJson(200, {
                    payload: {
                        data: [
                            {
                                accountId: CASH_ACCOUNT_ID,
                                accountUuid:
                                    '7ce69df2-674d-4da8-b8a1-f935686ecfa7',
                                accountType: 'CASH_ACCOUNT',
                                status: 'ACTIVE',
                                alias: MOCK_CASH_ACCOUNT_NAME,
                                iban: 'ES1215440000000000000001',
                                enabledBalance: '8500.50',
                                withheldBalance: '0',
                                currency: 'EUR',
                                creationDate: isoDateTimeDaysAgo(15),
                                holders: [{ me: true }],
                            },
                        ],
                    },
                })
            }

            if (
                apiPath ===
                    `/cperf-server/api/v2/cash-accounts/${CASH_ACCOUNT_ID}/remuneration` ||
                apiPath ===
                    '/account/api/v3/account/7ce69df2-674d-4da8-b8a1-f935686ecfa7/remuneration'
            ) {
                return sendJson(200, {
                    payload: {
                        data: {
                            remunerationPercentage: 2.5,
                            taePromotion: 0,
                        },
                    },
                })
            }

            if (
                apiPath ===
                '/cperf-server/api/v2/securities-accounts/self-basic'
            ) {
                return sendJson(200, {
                    payload: {
                        data: [
                            {
                                accountId: SEC_ACCOUNT_ID,
                                cashAccountId: CASH_ACCOUNT_ID,
                                status: 'ACTIVE',
                            },
                        ],
                    },
                })
            }

            if (apiPath === '/cards/api/v1/cards') {
                return sendJson(200, {
                    payload: {
                        data: [
                            {
                                cardId: CARD_ID,
                                accountId: CASH_ACCOUNT_ID,
                                cardType: 'DEBIT',
                                pan: '4548 **** **** 8899',
                                status: 'ACTIVATE',
                            },
                        ],
                    },
                })
            }

            if (apiPath === `/cards/api/v1/cards/${CARD_ID}/totals`) {
                return sendJson(200, {
                    payload: {
                        data: {
                            disposable: 6000.0,
                            limit: 6000.0,
                            consumedMonth: 145.75,
                        },
                    },
                })
            }

            if (apiPath === '/cperf-server/api/v2/deposits/self') {
                return sendJson(200, { payload: { data: [] } })
            }

            if (apiPath === '/loan/api/v1/credit-accounts/self') {
                return sendJson(200, { payload: { data: [] } })
            }

            if (
                apiPath ===
                `/cperf-server/api/v2/securities-accounts/${SEC_ACCOUNT_ID}`
            ) {
                return sendJson(200, {
                    payload: {
                        data: {
                            securitiesAccountInvestments: {
                                INDEXED_FUND: {
                                    investmentList: [
                                        {
                                            isin: MOCK_FUND_ISIN,
                                            investmentName: MOCK_FUND_NAME,
                                            marketCode: 'FUND',
                                            shares: '15.25',
                                            initialInvestment: '1500.00',
                                            initialInvestmentCurrency:
                                                '1500.00',
                                            originCurrencyLiquidationValue:
                                                '120.50',
                                            liquidationValueCurrency: 'EUR',
                                        },
                                    ],
                                },
                                BROKER: {
                                    investmentList: [
                                        {
                                            isin: MOCK_STOCK_ISIN,
                                            ticker: MOCK_STOCK_TICKER,
                                            stockId: 'stk-aapl',
                                            brokerProductType: 'RV',
                                            investmentName: MOCK_STOCK_NAME,
                                            marketCode: 'NSQ',
                                            shares: '10',
                                            initialInvestmentCurrency:
                                                '1800.00',
                                            originCurrencyLiquidationValue:
                                                '216.00',
                                            liquidationValueCurrency: 'USD',
                                        },
                                    ],
                                },
                            },
                        },
                    },
                })
            }

            if (apiPath === `/cperf-server/api/v2/funds/${MOCK_FUND_ISIN}`) {
                return sendJson(200, {
                    payload: {
                        data: {
                            name: MOCK_FUND_NAME,
                            assetType: 'VARIABLE_INCOME',
                            agent: 'Vanguard',
                            urlKiid: 'https://example.test/vanguard-kiid.pdf',
                        },
                    },
                })
            }

            if (
                apiPath ===
                `/cperf-server/api/v2/securities-accounts/${SEC_ACCOUNT_ID}/investment-summary/funds/${MOCK_FUND_ISIN}/added-values`
            ) {
                return sendJson(200, {
                    payload: {
                        data: { investmentAddedValue: 1500.0 },
                    },
                })
            }

            if (apiPath === '/cperf-server/api/v2/pension-accounts/self') {
                return sendJson(200, { payload: { data: [] } })
            }

            if (
                apiPath === '/cperf-server/api/v2/automatic-contributions/self'
            ) {
                return sendJson(200, {
                    payload: {
                        data: [
                            {
                                contributionType: 'ONE_DATE',
                                status: 'ACTIVE',
                                alias: MOCK_CONTRIBUTION_ALIAS,
                                fundName: MOCK_FUND_NAME,
                                isin: MOCK_FUND_ISIN,
                                toAccountType: 'SECURITIES_ACCOUNT',
                                amount: 250.0,
                                currency: 'EUR',
                                contributionTimeFrame: {
                                    recurrence: 'ONE_MONTH',
                                    startDate: '2026-01-01',
                                    endDate: null,
                                },
                            },
                        ],
                    },
                })
            }

            if (
                apiPath ===
                `/cperf-server/api/v2/securities-accounts/${SEC_ACCOUNT_ID}/orders`
            ) {
                return sendJson(200, {
                    payload: { data: buildFundOrdersStressList() },
                })
            }

            if (
                apiPath ===
                `/cperf-server/api/v2/securities-accounts/${SEC_ACCOUNT_ID}/orders/fund-ord-complete-1`
            ) {
                return sendJson(200, {
                    payload: {
                        data: {
                            orderDate: isoDateTimeDaysAgo(5),
                            executionDate: isoDateTimeDaysAgo(4),
                            executedShares: 4.1494,
                            liquidationValue: 120.5,
                            grossAmountOperationFundCurrency: 500.0,
                            netAmountFundCurrency: 500.0,
                            commissions: 0.0,
                            relatedOperations: [],
                        },
                    },
                })
            }

            if (apiPath === '/broker/v2/stock-orders') {
                return sendJson(200, {
                    payload: { data: buildStockOrdersStressList() },
                })
            }

            if (apiPath === '/broker/v2/stock-orders/stk-ord-complete-1') {
                return sendJson(200, {
                    payload: {
                        data: {
                            orderDate: isoDateTimeDaysAgo(6),
                            executionDate: isoDateTimeDaysAgo(5),
                            executedShares: 2.0,
                            priceCurrency: 205.5,
                            grossAmountOperationCurrency: 411.0,
                            netAmountCurrency: 412.5,
                            tradeCommissions: 1.5,
                            otherCommissions: 0.0,
                            instrumentIsin: MOCK_STOCK_ISIN,
                        },
                    },
                })
            }

            if (
                apiPath ===
                    `/cperf-server/api/v2/cash-accounts/${CASH_ACCOUNT_ID}/flows` ||
                apiPath ===
                    '/account/api/v3/account/7ce69df2-674d-4da8-b8a1-f935686ecfa7/flows'
            ) {
                return sendJson(200, {
                    payload: {
                        data: {
                            flowList: [
                                {
                                    reference: 'cash-mov-e2e-1',
                                    operationClass: 'TRANSFERENCIAS',
                                    operationType: 'TRANSFERENCIA',
                                    operationDate: isoDateTimeDaysAgo(3),
                                    currency: 'EUR',
                                    concept: ` ${MOCK_CASH_INFLOW_CONCEPT} `,
                                    amount: '2400.00',
                                },
                                {
                                    reference: 'cash-int-e2e-1',
                                    operationClass: '0',
                                    operationType: 'INTERESES S/F',
                                    operationDate: isoDateTimeDaysAgo(2),
                                    currency: 'EUR',
                                    concept: MOCK_CASH_INTEREST_CONCEPT,
                                    amount: '12.50',
                                },
                            ],
                        },
                    },
                })
            }

            if (apiPath === '/broker/v2/financial-events') {
                return sendJson(200, { payload: { data: [] } })
            }
        }

        if (pathname.startsWith('/__mock/external')) {
            return sendJson(200, {})
        }

        sendJson(404, { error: `Unhandled mock path: ${pathname}` })
    })

    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
    const port = (server.address() as AddressInfo).port

    return {
        port,
        requests,
        setFailEntityFetch: (fail: boolean) => {
            failEntityFetch = fail
        },
        clearRequests: () => {
            requests.length = 0
        },
        close: () =>
            new Promise<void>((resolve) => server.close(() => resolve())),
    }
}

export async function installEntityAndRatesMocks(
    serverPort: number,
): Promise<void> {
    const host = driver.isAndroid ? '10.0.2.2' : '127.0.0.1'
    const mockOrigin = `http://${host}:${serverPort}`

    await browser.execute((targetMockOrigin: string) => {
        const win = window as unknown as {
            __e2eMockOrigin?: string
            __e2eEntityMocksInstalled?: boolean
            __e2ePyodideWorkerErrors?: string[]
            Capacitor?: {
                nativePromise?: (
                    pluginName: string,
                    methodName: string,
                    options?: Record<string, unknown>,
                ) => Promise<unknown>
                Plugins?: Record<
                    string,
                    {
                        request?: (
                            options: Record<string, unknown>,
                        ) => Promise<unknown>
                    }
                >
            }
            TlsHttp?: {
                request?: (options: Record<string, unknown>) => Promise<unknown>
            }
            jsBridge?: {
                yahooFinance?: {
                    lookup?: (query: string, type: string) => Promise<string>
                    getInstrumentInfo?: (
                        query: string,
                        type: string,
                    ) => Promise<string>
                    getHistory?: (
                        query: string,
                        type: string,
                        fromDate: string,
                        toDate: string,
                    ) => Promise<string>
                    getSplits?: (
                        query: string,
                        type: string,
                        fromDate: string,
                        toDate: string,
                    ) => Promise<string>
                }
            }
        }

        win.__e2eMockOrigin = targetMockOrigin
        if (!Array.isArray(win.__e2ePyodideWorkerErrors)) {
            win.__e2ePyodideWorkerErrors = []
        }

        if (win.__e2eEntityMocksInstalled) {
            return
        }
        win.__e2eEntityMocksInstalled = true

        const origDebug = console.debug.bind(console)
        const origError = console.error.bind(console)
        const recordWorkerOutput = (prefix: unknown, body: unknown) => {
            const p = String(prefix ?? '')
            const text = String(body ?? '')
            if (p.includes('[Pyodide worker stderr]') && text.trim()) {
                win.__e2ePyodideWorkerErrors!.push(text)
                return
            }
            if (
                p.includes('[Pyodide worker stdout]') &&
                /(\|\s*ERROR\s*\||Traceback \(most recent call last\)|cannot convert float NaN to integer)/.test(
                    text,
                )
            ) {
                win.__e2ePyodideWorkerErrors!.push(text)
            }
        }

        console.debug = (...args: unknown[]) => {
            recordWorkerOutput(args[0], args[1])
            origDebug(...args)
        }
        console.error = (...args: unknown[]) => {
            recordWorkerOutput(args[0], args[1])
            origError(...args)
        }

        const normalizePlain = (val: unknown): unknown => {
            if (val instanceof Map) {
                const out: Record<string, unknown> = {}
                val.forEach((v, k) => {
                    out[String(k)] = normalizePlain(v)
                })
                return out
            }
            if (Array.isArray(val)) {
                return val.map(normalizePlain)
            }
            if (
                val &&
                typeof val === 'object' &&
                Object.getPrototypeOf(val) === Object.prototype
            ) {
                const out: Record<string, unknown> = {}
                for (const [k, v] of Object.entries(val)) {
                    out[k] = normalizePlain(v)
                }
                return out
            }
            return val
        }

        const rewriteExternalUrl = (rawUrl: string): string | null => {
            const base = win.__e2eMockOrigin!
            if (rawUrl.startsWith(base)) return null

            const rules: Array<[string, string]> = [
                ['https://features.api.finanze.me', `${base}/__mock/features`],
                ['https://api.myinvestor.es', `${base}/__mock/myinvestor-api`],
                [
                    'https://config.myinvestor.es',
                    `${base}/__mock/myinvestor-config`,
                ],
                [
                    'https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1',
                    `${base}/__mock/fx`,
                ],
                [
                    'https://latest.currency-api.pages.dev/v1',
                    `${base}/__mock/fx`,
                ],
                ['https://api.gold-api.com', `${base}/__mock/metals`],
                ['https://www.ft.com', `${base}/__mock/ft`],
            ]

            for (const [prefix, replacement] of rules) {
                if (rawUrl.startsWith(prefix)) {
                    return replacement + rawUrl.slice(prefix.length)
                }
            }

            if (
                rawUrl.startsWith('https://') &&
                !rawUrl.includes('127.0.0.1') &&
                !rawUrl.includes('10.0.2.2') &&
                !rawUrl.includes('localhost')
            ) {
                try {
                    const parsed = new URL(rawUrl)
                    return `${base}/__mock/external/${parsed.hostname}${parsed.pathname}${parsed.search}`
                } catch {
                    return null
                }
            }
            return null
        }

        const rewriteOptionsAndForward = (
            options: unknown,
            forward: (opts: Record<string, unknown>) => Promise<unknown>,
        ): Promise<unknown> => {
            const safeOpts = (normalizePlain(options) ?? {}) as Record<
                string,
                unknown
            >
            const rawUrl = String(safeOpts.url ?? '')
            const rewritten = rewriteExternalUrl(rawUrl)
            if (!rewritten) {
                return forward(safeOpts)
            }
            const headers =
                safeOpts.headers && typeof safeOpts.headers === 'object'
                    ? { ...(safeOpts.headers as Record<string, unknown>) }
                    : undefined
            if (headers) {
                delete headers.host
                delete headers.Host
            }
            return forward({
                ...safeOpts,
                ...(headers ? { headers } : {}),
                url: rewritten,
            })
        }

        if (
            win.Capacitor &&
            typeof win.Capacitor.nativePromise === 'function'
        ) {
            const origNativePromise = win.Capacitor.nativePromise.bind(
                win.Capacitor,
            )
            win.Capacitor.nativePromise = (
                pluginName: string,
                methodName: string,
                options?: Record<string, unknown>,
            ) => {
                if (
                    pluginName === 'CapacitorHttp' &&
                    methodName === 'request'
                ) {
                    return rewriteOptionsAndForward(options, (nextOpts) =>
                        origNativePromise(pluginName, methodName, nextOpts),
                    )
                }
                if (
                    pluginName === 'TlsHttpPlugin' &&
                    methodName === 'request'
                ) {
                    return rewriteOptionsAndForward(options, (nextOpts) =>
                        origNativePromise(pluginName, methodName, nextOpts),
                    )
                }
                return origNativePromise(pluginName, methodName, options)
            }
        }

        const origCapHttp = win.Capacitor?.Plugins?.CapacitorHttp
        if (origCapHttp?.request && win.Capacitor?.Plugins) {
            const origRequest = origCapHttp.request.bind(origCapHttp)
            win.Capacitor.Plugins.CapacitorHttp = new Proxy(origCapHttp, {
                get(target, prop, receiver) {
                    if (prop === 'request') {
                        return (options: Record<string, unknown>) =>
                            rewriteOptionsAndForward(options, origRequest)
                    }
                    return Reflect.get(target, prop, receiver)
                },
            })
        }

        if (win.TlsHttp?.request) {
            const origTlsRequest = win.TlsHttp.request.bind(win.TlsHttp)
            win.TlsHttp.request = (options: Record<string, unknown>) =>
                rewriteOptionsAndForward(options, origTlsRequest)
        }

        if (win.jsBridge?.yahooFinance) {
            const buildHistory = (query: string) => {
                const isUsd =
                    query.includes('037833') ||
                    query.toUpperCase().includes('AAPL')
                const currency = isUsd ? 'USD' : 'EUR'
                const basePrice = isUsd ? 200.25 : 118.4
                const points: Array<{ date: string; price: number }> = []
                const now = Date.now()
                for (let d = 60; d >= 0; d--) {
                    const dt = new Date(now - d * 86_400_000)
                    const iso = dt.toISOString().slice(0, 10)
                    points.push({
                        date: iso,
                        price: Number((basePrice + (60 - d) * 0.25).toFixed(2)),
                    })
                }
                return JSON.stringify({
                    symbol: isUsd ? 'AAPL' : '0P00000RQC.F',
                    currency,
                    points,
                })
            }

            win.jsBridge.yahooFinance.lookup = async (query: string) => {
                const isUsd =
                    query.includes('037833') ||
                    query.toUpperCase().includes('AAPL')
                return JSON.stringify([
                    {
                        symbol: isUsd ? 'AAPL' : '0P00000RQC.F',
                        name: isUsd
                            ? 'Apple USD E2E'
                            : 'Vanguard Global Stock E2E',
                        exchange: isUsd ? 'NMS' : 'FRA',
                        currency: isUsd ? 'USD' : 'EUR',
                        price: isUsd ? 216.0 : 120.5,
                        quoteType: isUsd ? 'EQUITY' : 'MUTUALFUND',
                    },
                ])
            }
            win.jsBridge.yahooFinance.getInstrumentInfo = async (
                query: string,
            ) => {
                const isUsd =
                    query.includes('037833') ||
                    query.toUpperCase().includes('AAPL')
                return JSON.stringify({
                    name: isUsd ? 'Apple USD E2E' : 'Vanguard Global Stock E2E',
                    currency: isUsd ? 'USD' : 'EUR',
                    symbol: isUsd ? 'AAPL' : '0P00000RQC.F',
                    price: isUsd ? 216.0 : 120.5,
                    type: isUsd ? 'STOCK' : 'MUTUAL_FUND',
                })
            }
            win.jsBridge.yahooFinance.getHistory = async (query: string) =>
                buildHistory(query)
            win.jsBridge.yahooFinance.getSplits = async () => JSON.stringify([])
        }
    }, mockOrigin)
}

export async function drainPyodideWorkerErrors(): Promise<string[]> {
    return browser.execute(() => {
        const win = window as unknown as {
            __e2ePyodideWorkerErrors?: string[]
        }
        const collected = [...(win.__e2ePyodideWorkerErrors ?? [])]
        win.__e2ePyodideWorkerErrors = []
        return collected
    })
}

export async function assertNoUnexpectedPyodideErrors(
    allowedPatterns: RegExp[] = [],
): Promise<void> {
    const errors = await drainPyodideWorkerErrors()
    const unexpected = errors.filter(
        (line) => !allowedPatterns.some((re) => re.test(line)),
    )
    if (unexpected.length > 0) {
        throw new Error(
            `Unexpected Pyodide worker error(s) detected:\n${unexpected.join('\n---\n')}`,
        )
    }
}
