import { test as base } from '@playwright/test'
import { spawn, type ChildProcess } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT || 7692)
const PROJECT_ROOT = join(import.meta.dirname, '..', '..', '..')

export interface BackendFixture {
    backendUrl: string
    dataDir: string
}

async function waitForBackend(url: string, timeoutMs = 30_000): Promise<void> {
    const start = Date.now()
    while (Date.now() - start < timeoutMs) {
        try {
            const res = await fetch(`${url}/api/v1/status`)
            if (res.ok) return
        } catch {
            // not ready yet
        }
        await new Promise((r) => setTimeout(r, 500))
    }
    throw new Error(`Backend did not start within ${timeoutMs}ms`)
}

export const test = base.extend<{}, { backend: BackendFixture }>({
    backend: [
        async ({}, use) => {
            const dataDir = mkdtempSync(join(tmpdir(), 'finanze-e2e-'))
            const backendUrl = `http://localhost:${BACKEND_PORT}`

            const proc: ChildProcess = spawn(
                'python',
                [
                    '-m',
                    'finanze',
                    '--port',
                    String(BACKEND_PORT),
                    '--data-dir',
                    dataDir,
                    '--log-level',
                    'DEBUG',
                ],
                {
                    cwd: PROJECT_ROOT,
                    env: {
                        ...process.env,
                        E2E_TEST_MODE: '1',
                        ENV_FF: '1',
                        POSITION_UPDATE_COOLDOWN_SECONDS: '0',
                        CRYPTO_POSITION_UPDATE_COOLDOWN: '0',
                        PYTHONPATH: [
                            join(PROJECT_ROOT, 'tests'),
                            join(PROJECT_ROOT, 'finanze'),
                        ].join(':'),
                    },
                    stdio: ['ignore', 'pipe', 'pipe'],
                },
            )

            proc.stdout?.on('data', (data) => {
                process.stdout.write(`[backend] ${data}`)
            })
            proc.stderr?.on('data', (data) => {
                process.stderr.write(`[backend] ${data}`)
            })

            await waitForBackend(backendUrl)

            await use({ backendUrl, dataDir })

            proc.kill('SIGTERM')
            await new Promise<void>((resolve) => {
                const timeout = setTimeout(() => {
                    proc.kill('SIGKILL')
                    resolve()
                }, 5_000)
                proc.on('close', () => {
                    clearTimeout(timeout)
                    resolve()
                })
            })

            rmSync(dataDir, { recursive: true, force: true })
        },
        { scope: 'worker' },
    ],
})
