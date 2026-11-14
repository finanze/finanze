import { createServer, type IncomingMessage, type Server } from 'node:http'
import type { AddressInfo } from 'node:net'

export interface ChatCall {
    model: string
    body: Record<string, unknown>
}

export interface MockReply {
    status: number
    body: unknown
}

type ReplyFn = (call: ChatCall) => MockReply | Promise<MockReply>

export interface AIMockServer {
    url: string
    calls: ChatCall[]
    setReply: (reply: ReplyFn) => void
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

export function chatCompletion(content: unknown): MockReply {
    return {
        status: 200,
        body: {
            choices: [
                {
                    finish_reason: 'stop',
                    message: {
                        role: 'assistant',
                        content: JSON.stringify(content),
                    },
                },
            ],
        },
    }
}

export async function startAIMockServer(
    models: string[],
): Promise<AIMockServer> {
    const calls: ChatCall[] = []
    let reply: ReplyFn = () => chatCompletion({ rows: [] })

    const server: Server = createServer(async (request, response) => {
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
            const call = { model: String(body.model), body }
            calls.push(call)
            const result = await reply(call)
            return send(result.status, result.body)
        }
        send(404, { error: 'not found' })
    })

    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
    const { port } = server.address() as AddressInfo
    return {
        url: `http://127.0.0.1:${port}/v1`,
        calls,
        setReply: (next) => {
            reply = next
        },
        close: () =>
            new Promise<void>((resolve) => server.close(() => resolve())),
    }
}
