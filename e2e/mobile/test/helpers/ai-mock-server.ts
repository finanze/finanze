import { createServer, type IncomingMessage } from 'node:http'
import type { AddressInfo } from 'node:net'

export interface ChatCall {
    model: string
    body: Record<string, unknown>
}

type Rows = Record<string, unknown>[]
export type MockRows = Rows | ((call: number) => Rows)

export interface AIMockServer {
    port: number
    calls: ChatCall[]
    setRows: (rows: MockRows) => void
    close: () => Promise<void>
}

function readJson(request: IncomingMessage): Promise<Record<string, unknown>> {
    return new Promise((resolve, reject) => {
        const chunks: Buffer[] = []
        request.on('data', (chunk) => chunks.push(chunk))
        request.on('end', () => {
            try {
                resolve(JSON.parse(Buffer.concat(chunks).toString() || '{}'))
            } catch (error) {
                reject(error)
            }
        })
        request.on('error', reject)
    })
}

export async function startAIMockServer(
    models: string[],
    rows: MockRows,
): Promise<AIMockServer> {
    const calls: ChatCall[] = []
    const rowsFor = (next: MockRows) =>
        typeof next === 'function' ? next : () => next
    let reply = rowsFor(rows)
    const server = createServer(async (request, response) => {
        const send = (status: number, body: unknown) => {
            response.writeHead(status, { 'Content-Type': 'application/json' })
            response.end(JSON.stringify(body))
        }
        if (request.method === 'GET' && request.url === '/v1/models') {
            return send(200, {
                data: models.map((id) => ({ id, object: 'model' })),
            })
        }
        if (
            request.method === 'POST' &&
            request.url === '/v1/chat/completions'
        ) {
            const body = await readJson(request)
            calls.push({ model: String(body.model), body })
            return send(200, {
                choices: [
                    {
                        finish_reason: 'stop',
                        message: {
                            role: 'assistant',
                            content: JSON.stringify({
                                rows: reply(calls.length - 1),
                            }),
                        },
                    },
                ],
            })
        }
        send(404, { error: 'not found' })
    })

    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
    return {
        port: (server.address() as AddressInfo).port,
        calls,
        setRows: (next) => {
            reply = rowsFor(next)
        },
        close: () =>
            new Promise<void>((resolve) => server.close(() => resolve())),
    }
}

// The Android emulator reaches the host loopback through 10.0.2.2.
export function deviceBaseUrl(port: number): string {
    const host = driver.isAndroid ? '10.0.2.2' : '127.0.0.1'
    return `http://${host}:${port}/v1`
}
