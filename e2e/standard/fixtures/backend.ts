import { test as base } from "@playwright/test";
import { spawn, type ChildProcess } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";

const DEFAULT_BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT || 7692);
export const PROJECT_ROOT = join(import.meta.dirname, "..", "..", "..");
export const PYTHON_BIN = process.env.PYTHON || "python";
export const PYTHON_PATH = [
  join(PROJECT_ROOT, "tests"),
  join(PROJECT_ROOT, "finanze"),
].join(delimiter);

export interface BackendFixture {
  backendUrl: string;
  dataDir: string;
}

export async function waitForBackend(
  url: string,
  timeoutMs = 30_000,
): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${url}/api/v1/status`);
      if (res.ok) return;
    } catch {
      // not ready yet
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error(`Backend did not start within ${timeoutMs}ms`);
}

export async function stopBackendProcess(proc: ChildProcess): Promise<void> {
  if (proc.exitCode !== null) return;

  await new Promise<void>((resolve) => {
    const timeout = setTimeout(() => {
      try {
        proc.kill("SIGKILL");
      } catch {
        proc.kill();
      }
      resolve();
    }, 5_000);
    proc.once("close", () => {
      clearTimeout(timeout);
      resolve();
    });
    proc.kill("SIGTERM");
  });
}

export function removeDataDir(dataDir: string): void {
  rmSync(dataDir, {
    recursive: true,
    force: true,
    maxRetries: 5,
    retryDelay: 200,
  });
}

export const test = base.extend<
  {},
  { backendPort: number; backend: BackendFixture }
>({
  backendPort: [DEFAULT_BACKEND_PORT, { scope: "worker", option: true }],
  backend: [
    async ({ backendPort }, use) => {
      const dataDir = mkdtempSync(join(tmpdir(), "finanze-e2e-"));
      const backendUrl = `http://localhost:${backendPort}`;

      const proc: ChildProcess = spawn(
        PYTHON_BIN,
        [
          "-m",
          "finanze",
          "--port",
          String(backendPort),
          "--data-dir",
          dataDir,
          "--log-level",
          "DEBUG",
        ],
        {
          cwd: PROJECT_ROOT,
          env: {
            ...process.env,
            E2E_TEST_MODE: "1",
            ENV_FF: "1",
            POSITION_UPDATE_COOLDOWN_SECONDS: "0",
            CRYPTO_POSITION_UPDATE_COOLDOWN: "0",
            PYTHONPATH: PYTHON_PATH,
          },
          stdio: ["ignore", "pipe", "pipe"],
        },
      );

      proc.stdout?.on("data", (data) => {
        process.stdout.write(`[backend] ${data}`);
      });
      proc.stderr?.on("data", (data) => {
        process.stderr.write(`[backend] ${data}`);
      });

      await waitForBackend(backendUrl);

      await use({ backendUrl, dataDir });

      await stopBackendProcess(proc);
      removeDataDir(dataDir);
    },
    { scope: "worker" },
  ],
});
