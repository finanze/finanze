import {
    createCipheriv,
    createDecipheriv,
    createHash,
    createHmac,
    pbkdf2Sync,
    randomBytes,
    randomUUID,
    timingSafeEqual,
} from 'node:crypto'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { createServer, type IncomingMessage, type Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { DatabaseSync } from 'node:sqlite'
import { deflateSync, inflateSync } from 'node:zlib'

function deviceOriginUrl(port: number): string {
    const host = driver.isAndroid ? '10.0.2.2' : '127.0.0.1'
    return `http://${host}:${port}`
}

export interface StoredBackupPiece {
    id: string
    protocol: number
    date: string
    type: 'DATA' | 'CONFIG'
    size: number
    schema_revision?: number
    schema_hash?: string
    payload: Buffer
}

export type PayloadMutationMode =
    | 'ahead_of_time'
    | 'mid_upgrade_failure'
    | 'corrupt_file'
    | 'backdate_last_update'

export interface MobileCloudBackupMockServer {
    port: number
    url: string
    getDownloadCount: () => number
    getDataPiece: () => StoredBackupPiece | null
    setDataPiece: (piece: StoredBackupPiece) => Promise<void>
    restoreDataPieceAsNewer: (
        piece: StoredBackupPiece,
        overrides?: Partial<Omit<StoredBackupPiece, 'payload' | 'size'>>,
    ) => Promise<StoredBackupPiece>
    mutateDataPiece: (params: {
        basePayload: Buffer
        password: string
        mode: Exclude<PayloadMutationMode, 'backdate_last_update'>
        schema_revision?: number
    }) => Promise<StoredBackupPiece>
    createBackdatedBackupPiece: (params: {
        piece: StoredBackupPiece
        password: string
        date: string
    }) => StoredBackupPiece
    clear: () => Promise<void>
    close: () => Promise<void>
}

const BACKUP_SALT = Buffer.from('finanze-backup-salt', 'utf8')
const PBKDF2_ITERATIONS = 100_000
const FERNET_VERSION = 0x80

function deriveFernetKeys(userPassword: string): {
    signingKey: Buffer
    encryptionKey: Buffer
} {
    const hashedPassword = createHash('sha3-256')
        .update(userPassword, 'utf8')
        .digest('hex')
    const derived = pbkdf2Sync(
        Buffer.from(hashedPassword, 'utf8'),
        BACKUP_SALT,
        PBKDF2_ITERATIONS,
        32,
        'sha256',
    )
    return {
        signingKey: derived.subarray(0, 16),
        encryptionKey: derived.subarray(16, 32),
    }
}

export function compileBackupV1(
    sqliteBytes: Buffer,
    userPassword: string,
): Buffer {
    const compressed = deflateSync(sqliteBytes, { level: 9 })
    const { signingKey, encryptionKey } = deriveFernetKeys(userPassword)

    const version = Buffer.from([FERNET_VERSION])
    const timestamp = Buffer.alloc(8)
    timestamp.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 1000)))
    const iv = randomBytes(16)

    const cipher = createCipheriv('aes-128-cbc', encryptionKey, iv)
    const ciphertext = Buffer.concat([
        cipher.update(compressed),
        cipher.final(),
    ])

    const headerAndBody = Buffer.concat([version, timestamp, iv, ciphertext])
    const hmac = createHmac('sha256', signingKey).update(headerAndBody).digest()

    return Buffer.concat([headerAndBody, hmac])
}

export function decompileBackupV1(
    payload: Buffer,
    userPassword: string,
): Buffer {
    if (payload.length < 57 || payload[0] !== FERNET_VERSION) {
        throw new Error('Invalid BackupProcessorV1 binary Fernet token')
    }

    const { signingKey, encryptionKey } = deriveFernetKeys(userPassword)
    const headerAndBody = payload.subarray(0, payload.length - 32)
    const expectedHmac = payload.subarray(payload.length - 32)
    const actualHmac = createHmac('sha256', signingKey)
        .update(headerAndBody)
        .digest()

    if (!timingSafeEqual(actualHmac, expectedHmac)) {
        throw new Error('INVALID_CREDENTIALS: Fernet HMAC mismatch')
    }

    const iv = payload.subarray(9, 25)
    const ciphertext = payload.subarray(25, payload.length - 32)
    const decipher = createDecipheriv('aes-128-cbc', encryptionKey, iv)
    const compressed = Buffer.concat([
        decipher.update(ciphertext),
        decipher.final(),
    ])

    return inflateSync(compressed)
}

export function mutateEncryptedPayload(
    basePayload: Buffer,
    password: string,
    mode: PayloadMutationMode,
    extraArg = '',
): Buffer {
    if (mode === 'corrupt_file') {
        return compileBackupV1(
            Buffer.from('not-a-valid-sqlite3-database-file-header', 'utf8'),
            password,
        )
    }

    const sqliteBytes = decompileBackupV1(basePayload, password)
    const workDir = mkdtempSync(join(tmpdir(), 'finanze-mobile-e2e-mutate-'))
    try {
        const dbPath = join(workDir, 'backup.sqlite')
        writeFileSync(dbPath, sqliteBytes)

        const db = new DatabaseSync(dbPath)
        try {
            if (mode === 'ahead_of_time') {
                db.exec(
                    "INSERT INTO migrations (version, applied_at, name) VALUES (9999, '2099-01-01T00:00:00+00:00', 'v99.0.0:0_future_migration')",
                )
            } else if (mode === 'mid_upgrade_failure') {
                db.exec(
                    'DELETE FROM migrations WHERE version = (SELECT MAX(version) FROM migrations)',
                )
                db.exec(
                    "CREATE TRIGGER fail_upgrade BEFORE INSERT ON migrations BEGIN SELECT RAISE(ABORT, 'simulated mid-upgrade failure'); END",
                )
            } else if (mode === 'backdate_last_update') {
                const stmt = db.prepare(
                    'UPDATE sys_config SET value = ? WHERE "key" = ?',
                )
                stmt.run(extraArg, 'last_update')
            }
        } finally {
            db.close()
        }

        return compileBackupV1(readFileSync(dbPath), password)
    } finally {
        rmSync(workDir, {
            recursive: true,
            force: true,
            maxRetries: 5,
            retryDelay: 100,
        })
    }
}

function readBuffer(request: IncomingMessage): Promise<Buffer> {
    return new Promise((resolve, reject) => {
        const chunks: Buffer[] = []
        request.on('data', (chunk) => chunks.push(Buffer.from(chunk)))
        request.on('end', () => resolve(Buffer.concat(chunks)))
        request.on('error', reject)
    })
}

function serializePieceMeta(piece: StoredBackupPiece) {
    return {
        id: piece.id,
        protocol: piece.protocol,
        date: piece.date,
        type: piece.type,
        size: piece.size,
        ...(piece.schema_revision !== undefined ? { schema_revision: piece.schema_revision } : {}),
        ...(piece.schema_hash !== undefined ? { schema_hash: piece.schema_hash } : {}),
    }
}

async function waitForBackendInfoCacheExpiry(): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve, 1_150))
}

export async function startMobileCloudBackupMockServer(): Promise<MobileCloudBackupMockServer> {
    const pieces = new Map<string, StoredBackupPiece>()
    const stagedUploads = new Map<string, Omit<StoredBackupPiece, 'payload'>>()
    let downloadCount = 0
    let port = 0

    const server: Server = createServer(async (request, response) => {
        const sendJson = (status: number, body: unknown) => {
            response.writeHead(status, { 'Content-Type': 'application/json' })
            response.end(JSON.stringify(body))
        }

        const rawHost = request.headers.host ?? ''
        const safeHost =
            rawHost.startsWith('127.0.0.1:') ||
            rawHost.startsWith('10.0.2.2:') ||
            rawHost.startsWith('localhost:')
                ? rawHost
                : `127.0.0.1:${port}`
        const origin = `http://${safeHost}`
        const parsedUrl = new URL(request.url ?? '/', origin)
        const { pathname, searchParams } = parsedUrl

        if (request.method === 'GET' && pathname === '/v1/backups') {
            const out: Record<
                string,
                ReturnType<typeof serializePieceMeta>
            > = {}
            for (const [type, piece] of pieces.entries()) {
                out[type] = serializePieceMeta(piece)
            }
            return sendJson(200, { pieces: out })
        }

        if (request.method === 'POST' && pathname === '/v1/backups/upload') {
            const raw = await readBuffer(request)
            const body = JSON.parse(raw.toString() || '{}') as {
                pieces?: Array<{
                    id: string
                    type: 'DATA' | 'CONFIG'
                    size: number
                    date: string
                    protocol: number
                    schema_revision?: number
                    schema_hash?: string
                }>
            }
            const uploads = (body.pieces ?? []).map((piece) => {
                const token = randomUUID()
                stagedUploads.set(token, {
                    id: piece.id,
                    type: piece.type,
                    size: piece.size,
                    date: piece.date,
                    protocol: piece.protocol,
                    ...(piece.schema_revision !== undefined
                        ? { schema_revision: piece.schema_revision }
                        : {}),
                    ...(piece.schema_hash !== undefined
                        ? { schema_hash: piece.schema_hash }
                        : {}),
                })
                const headers: Record<string, string> = {
                    'Content-Type': 'application/octet-stream',
                    'x-amz-meta-id': piece.id,
                    'x-amz-meta-protocol': String(piece.protocol),
                    'x-amz-meta-date': piece.date,
                    'x-amz-meta-type': piece.type,
                }
                if (piece.schema_revision !== undefined) {
                    headers['x-amz-meta-schema_revision'] = String(piece.schema_revision)
                }
                if (piece.schema_hash !== undefined) {
                    headers['x-amz-meta-schema_hash'] = piece.schema_hash
                }
                return {
                    type: piece.type,
                    method: 'PUT',
                    url: `${origin}/r2/${piece.type}?token=${token}`,
                    headers,
                }
            })
            return sendJson(200, { uploads })
        }

        if (request.method === 'PUT' && pathname.startsWith('/r2/')) {
            const token = searchParams.get('token') ?? ''
            const staged = stagedUploads.get(token)
            if (!staged) {
                return sendJson(400, { error: 'Invalid upload token' })
            }
            const payload = await readBuffer(request)
            stagedUploads.delete(token)
            const rawHeaderRevision = request.headers['x-amz-meta-schema_revision']
            const parsedRevision =
                typeof rawHeaderRevision === 'string'
                    ? Number.parseInt(rawHeaderRevision, 10)
                    : staged.schema_revision
            const rawHeaderHash = request.headers['x-amz-meta-schema_hash']
            const parsedHash =
                typeof rawHeaderHash === 'string'
                    ? rawHeaderHash
                    : staged.schema_hash
            pieces.set(staged.type, {
                ...staged,
                size: payload.length,
                ...(parsedRevision !== undefined && !Number.isNaN(parsedRevision)
                    ? { schema_revision: parsedRevision }
                    : {}),
                ...(parsedHash !== undefined ? { schema_hash: parsedHash } : {}),
                payload,
            })
            response.writeHead(200)
            response.end()
            return
        }

        if (request.method === 'GET' && pathname === '/v1/backups/download') {
            const requestedTypes = searchParams.getAll('type')
            const out: Record<
                string,
                ReturnType<typeof serializePieceMeta> & { url: string }
            > = {}
            for (const type of requestedTypes) {
                const piece = pieces.get(type)
                if (!piece) continue
                out[type] = {
                    ...serializePieceMeta(piece),
                    url: `${origin}/r2/${type}`,
                }
            }
            return sendJson(200, { pieces: out })
        }

        if (request.method === 'GET' && pathname.startsWith('/r2/')) {
            const type = pathname.slice('/r2/'.length)
            const piece = pieces.get(type)
            if (!piece) {
                return sendJson(404, { error: 'Piece not found' })
            }
            downloadCount += 1
            response.writeHead(200, {
                'Content-Type': 'application/octet-stream',
                'Content-Length': String(piece.payload.length),
            })
            response.end(piece.payload)
            return
        }

        sendJson(404, { error: 'Not found' })
    })

    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
    port = (server.address() as AddressInfo).port
    const baseUrl = `http://127.0.0.1:${port}`

    let bumpCounter = 1
    const nextFutureIsoDate = (fromIso?: string) => {
        const baseMs = Math.max(Date.now(), fromIso ? Date.parse(fromIso) : 0)
        bumpCounter += 1
        return new Date(baseMs + bumpCounter * 60_000).toISOString()
    }

    return {
        port,
        url: baseUrl,
        getDownloadCount: () => downloadCount,
        getDataPiece: () => {
            const piece = pieces.get('DATA')
            return piece
                ? { ...piece, payload: Buffer.from(piece.payload) }
                : null
        },
        setDataPiece: async (piece) => {
            pieces.set('DATA', {
                ...piece,
                size: piece.payload.length,
                payload: Buffer.from(piece.payload),
            })
            await waitForBackendInfoCacheExpiry()
        },
        restoreDataPieceAsNewer: async (piece, overrides = {}) => {
            const current = pieces.get('DATA')
            const updated: StoredBackupPiece = {
                id: overrides.id ?? randomUUID(),
                protocol: overrides.protocol ?? piece.protocol,
                date:
                    overrides.date ??
                    nextFutureIsoDate(current?.date ?? piece.date),
                type: 'DATA',
                size: piece.payload.length,
                ...(overrides.schema_revision !== undefined
                    ? { schema_revision: overrides.schema_revision }
                    : piece.schema_revision !== undefined
                      ? { schema_revision: piece.schema_revision }
                      : {}),
                ...(overrides.schema_hash !== undefined
                    ? { schema_hash: overrides.schema_hash }
                    : piece.schema_hash !== undefined
                      ? { schema_hash: piece.schema_hash }
                      : {}),
                payload: Buffer.from(piece.payload),
            }
            pieces.set('DATA', updated)
            await waitForBackendInfoCacheExpiry()
            return updated
        },
        mutateDataPiece: async ({ basePayload, password, mode, schema_revision }) => {
            const mutatedPayload = mutateEncryptedPayload(
                basePayload,
                password,
                mode,
            )
            const current = pieces.get('DATA')
            const updated: StoredBackupPiece = {
                id: randomUUID(),
                protocol: 1,
                date: nextFutureIsoDate(current?.date),
                type: 'DATA',
                size: mutatedPayload.length,
                ...(schema_revision !== undefined ? { schema_revision } : {}),
                payload: mutatedPayload,
            }
            pieces.set('DATA', updated)
            await waitForBackendInfoCacheExpiry()
            return updated
        },
        createBackdatedBackupPiece: ({ piece, password, date }) => {
            const payload = mutateEncryptedPayload(
                piece.payload,
                password,
                'backdate_last_update',
                date,
            )
            return {
                ...piece,
                id: randomUUID(),
                date,
                size: payload.length,
                payload,
            }
        },
        clear: async () => {
            pieces.clear()
            stagedUploads.clear()
            await waitForBackendInfoCacheExpiry()
        },
        close: () =>
            new Promise<void>((resolve) => server.close(() => resolve())),
    }
}

function encodeBase64Url(obj: Record<string, unknown>): string {
    return Buffer.from(JSON.stringify(obj)).toString('base64url')
}

export function createMockCloudJwt(
    email = 'mobile-cloud@finanze.test',
): string {
    const header = encodeBase64Url({ kid: email, alg: 'HS256', typ: 'JWT' })
    const payload = encodeBase64Url({
        sub: 'mock-mobile-user-id-e2e',
        email,
        user_role: 'PLUS',
        permissions: [
            'backup.info',
            'backup.create',
            'backup.import',
            'backup.erase',
            'backup.auto',
        ],
        exp: Math.floor(Date.now() / 1000) + 3600,
    })
    const signature = Buffer.from('e2e-mock-hmac-sha256-signature!!').toString(
        'base64url',
    )
    return `${header}.${payload}.${signature}`
}

export async function installMobileCloudMocks(
    serverPort: number,
    email = 'mobile-cloud@finanze.test',
): Promise<void> {
    const cloudBaseUrl = deviceOriginUrl(serverPort)
    const accessToken = createMockCloudJwt(email)
    const nowIso = new Date().toISOString()

    await browser.execute(
        (
            targetCloudBaseUrl: string,
            targetEmail: string,
            jwt: string,
            iso: string,
        ) => {
            const win = window as unknown as {
                __e2eCloudConfig?: {
                    cloudBaseUrl: string
                    email: string
                    jwt: string
                    iso: string
                }
                __e2eCloudInstalled?: boolean
                Capacitor?: {
                    nativePromise?: (
                        pluginName: string,
                        methodName: string,
                        options?: Record<string, unknown>,
                    ) => Promise<unknown>
                    Plugins?: Record<
                        string,
                        {
                            request: (
                                options: Record<string, unknown>,
                            ) => Promise<unknown>
                        }
                    >
                }
            }

            win.__e2eCloudConfig = {
                cloudBaseUrl: targetCloudBaseUrl,
                email: targetEmail,
                jwt,
                iso,
            }

            if (win.__e2eCloudInstalled) {
                return
            }
            win.__e2eCloudInstalled = true

            const buildSupabaseSession = () => {
                const cfg = win.__e2eCloudConfig!
                const userPayload = {
                    id: 'mock-mobile-user-id-e2e',
                    aud: 'authenticated',
                    role: 'authenticated',
                    email: cfg.email,
                    email_confirmed_at: cfg.iso,
                    app_metadata: { provider: 'email', providers: ['email'] },
                    user_metadata: {},
                    identities: [
                        {
                            id: 'mock-mobile-identity-id',
                            user_id: 'mock-mobile-user-id-e2e',
                            identity_data: { email: cfg.email },
                            provider: 'email',
                            created_at: cfg.iso,
                            updated_at: cfg.iso,
                        },
                    ],
                    created_at: cfg.iso,
                    updated_at: cfg.iso,
                }
                const sessionPayload = {
                    access_token: cfg.jwt,
                    token_type: 'bearer',
                    expires_in: 3600,
                    expires_at: Math.floor(Date.now() / 1000) + 3600,
                    refresh_token: 'mock-mobile-refresh-token-e2e',
                    user: userPayload,
                }
                return { userPayload, sessionPayload }
            }

            const origFetch = window.fetch.bind(window)
            window.fetch = async (
                input: RequestInfo | URL,
                init?: RequestInit,
            ): Promise<Response> => {
                const rawUrl =
                    typeof input === 'string'
                        ? input
                        : input instanceof URL
                          ? input.href
                          : input.url
                if (rawUrl.includes('/auth/v1/token')) {
                    const { sessionPayload } = buildSupabaseSession()
                    return new Response(JSON.stringify(sessionPayload), {
                        status: 200,
                        headers: { 'Content-Type': 'application/json' },
                    })
                }
                if (rawUrl.includes('/auth/v1/user')) {
                    const { userPayload } = buildSupabaseSession()
                    return new Response(JSON.stringify(userPayload), {
                        status: 200,
                        headers: { 'Content-Type': 'application/json' },
                    })
                }
                if (rawUrl.includes('/auth/v1/logout')) {
                    return new Response('', { status: 204 })
                }
                return origFetch(input, init)
            }

            const normalizeCapOptions = (val: unknown): unknown => {
                if (val instanceof Map) {
                    const obj: Record<string, unknown> = {}
                    val.forEach((v, k) => {
                        obj[String(k)] = normalizeCapOptions(v)
                    })
                    return obj
                }
                if (Array.isArray(val)) {
                    return val.map(normalizeCapOptions)
                }
                if (
                    val &&
                    typeof val === 'object' &&
                    Object.getPrototypeOf(val) === Object.prototype
                ) {
                    const obj: Record<string, unknown> = {}
                    for (const [k, v] of Object.entries(val)) {
                        obj[k] = normalizeCapOptions(v)
                    }
                    return obj
                }
                return val
            }

            const interceptCapHttpOptions = (
                options: unknown,
                forward: (opts: Record<string, unknown>) => Promise<unknown>,
            ): Promise<unknown> => {
                const safeOpts = (normalizeCapOptions(options) ?? {}) as Record<
                    string,
                    unknown
                >
                const rawUrl = String(safeOpts.url ?? '')
                if (rawUrl.startsWith('https://features.api.finanze.me')) {
                    return Promise.resolve({
                        status: 200,
                        headers: { 'content-type': 'application/json' },
                        data: {
                            features: {
                                CLOUD: {
                                    ON: { target: [{ type: 'ALL' }] },
                                },
                            },
                        },
                        url: rawUrl,
                    })
                }
                if (rawUrl.includes('/auth/v1/token')) {
                    const { sessionPayload } = buildSupabaseSession()
                    return Promise.resolve({
                        status: 200,
                        headers: { 'content-type': 'application/json' },
                        data: sessionPayload,
                        url: rawUrl,
                    })
                }
                if (rawUrl.includes('/auth/v1/user')) {
                    const { userPayload } = buildSupabaseSession()
                    return Promise.resolve({
                        status: 200,
                        headers: { 'content-type': 'application/json' },
                        data: userPayload,
                        url: rawUrl,
                    })
                }
                if (rawUrl.includes('/auth/v1/logout')) {
                    return Promise.resolve({
                        status: 204,
                        headers: {},
                        data: '',
                        url: rawUrl,
                    })
                }
                if (rawUrl.startsWith('https://api.finanze.me')) {
                    const rewrittenUrl = rawUrl.replace(
                        'https://api.finanze.me',
                        win.__e2eCloudConfig!.cloudBaseUrl,
                    )
                    const rawHeaders =
                        safeOpts.headers && typeof safeOpts.headers === 'object'
                            ? {
                                  ...(safeOpts.headers as Record<
                                      string,
                                      unknown
                                  >),
                              }
                            : undefined
                    if (rawHeaders) {
                        delete rawHeaders.host
                        delete rawHeaders.Host
                    }
                    return forward({
                        ...safeOpts,
                        ...(rawHeaders ? { headers: rawHeaders } : {}),
                        url: rewrittenUrl,
                    })
                }
                return forward(safeOpts)
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
                    if (pluginName === 'CapacitorHttp') {
                        return interceptCapHttpOptions(options, (nextOpts) =>
                            origNativePromise(pluginName, methodName, nextOpts),
                        )
                    }
                    return origNativePromise(pluginName, methodName, options)
                }
            }

            const origCapHttp = win.Capacitor?.Plugins?.CapacitorHttp
            if (origCapHttp && win.Capacitor?.Plugins) {
                const origRequest = origCapHttp.request.bind(origCapHttp)
                win.Capacitor.Plugins.CapacitorHttp = new Proxy(origCapHttp, {
                    get(target, prop, receiver) {
                        if (prop === 'request') {
                            return (options: Record<string, unknown>) =>
                                interceptCapHttpOptions(options, origRequest)
                        }
                        return Reflect.get(target, prop, receiver)
                    },
                })
            }

            const patchedWorkers = new WeakSet<Worker>()
            const origPostMessage = Worker.prototype.postMessage
            Worker.prototype.postMessage = function (
                this: Worker,
                message: unknown,
                ...rest: unknown[]
            ) {
                const msg = message as {
                    kind?: string
                    action?: string
                    payload?: { modulePath?: string }
                }
                if (
                    !patchedWorkers.has(this) &&
                    msg?.kind === 'req' &&
                    msg?.action === 'callPythonFunction' &&
                    msg?.payload?.modulePath === 'controller'
                ) {
                    patchedWorkers.add(this)
                    origPostMessage.call(this, {
                        kind: 'req',
                        id: -9001,
                        action: 'runPythonAsync',
                        payload: {
                            code: [
                                'import init',
                                'from domain.status import FFStatus',
                                'if init.app and init.app.ff_client:',
                                "    init.app.ff_client._features['CLOUD'] = FFStatus.ON",
                            ].join('\n'),
                        },
                    })
                }
                return (
                    origPostMessage as (
                        message: unknown,
                        ...args: unknown[]
                    ) => void
                ).call(this, message, ...rest)
            }
        },
        cloudBaseUrl,
        email,
        accessToken,
        nowIso,
    )
}
