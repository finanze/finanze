import { test as base } from "@playwright/test";
import { spawn, type ChildProcess } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  PROJECT_ROOT,
  PYTHON_BIN,
  PYTHON_PATH,
  removeDataDir,
  stopBackendProcess,
  waitForBackend,
} from "./backend";
import {
  startCloudBackupMockServer,
  type CloudBackupMockServer,
} from "../helpers/cloud-backup-mock-server";

const DEFAULT_CLOUD_BACKEND_PORT = Number(
  process.env.E2E_CLOUD_BACKEND_PORT || 7694,
);

export interface CloudBackendController {
  backendUrl: string;
  readonly dataDir: string;
  resetToFreshInstance: () => Promise<void>;
}

function createQuotedTempDataDir(): string {
  return mkdtempSync(join(tmpdir(), "finanze-e2e-o'hare-"));
}

function spawnCloudBackend(
  port: number,
  dataDir: string,
  cloudUrl: string,
): ChildProcess {
  const proc = spawn(
    PYTHON_BIN,
    [
      "-m",
      "finanze",
      "--port",
      String(port),
      "--data-dir",
      dataDir,
      "--log-level",
      "DEBUG",
    ],
    {
      cwd: PROJECT_ROOT,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1",
        E2E_TEST_MODE: "1",
        ENV_FF: "1",
        FF_CLOUD: "ON",
        FF_PLUS: "ON",
        CLOUD_URL: cloudUrl,
        POSITION_UPDATE_COOLDOWN_SECONDS: "0",
        CRYPTO_POSITION_UPDATE_COOLDOWN: "0",
        PYTHONPATH: PYTHON_PATH,
      },
      stdio: ["ignore", "pipe", "pipe"],
    },
  );

  proc.stdout?.on("data", (data) => {
    process.stdout.write(`[cloud-backend] ${data}`);
  });
  proc.stderr?.on("data", (data) => {
    process.stderr.write(`[cloud-backend] ${data}`);
  });

  return proc;
}

export const test = base.extend<
  { cloudBackend: CloudBackendController },
  { backendPort: number; cloudServer: CloudBackupMockServer }
>({
  backendPort: [DEFAULT_CLOUD_BACKEND_PORT, { scope: "worker", option: true }],
  cloudServer: [
    async ({}, use) => {
      const server = await startCloudBackupMockServer();
      await use(server);
      await server.close();
    },
    { scope: "worker" },
  ],
  cloudBackend: async ({ backendPort, cloudServer }, use) => {
    await cloudServer.clear();

    let currentDataDir = createQuotedTempDataDir();
    const backendUrl = `http://localhost:${backendPort}`;
    let proc = spawnCloudBackend(backendPort, currentDataDir, cloudServer.url);
    await waitForBackend(backendUrl);

    const controller: CloudBackendController = {
      backendUrl,
      get dataDir() {
        return currentDataDir;
      },
      resetToFreshInstance: async () => {
        await stopBackendProcess(proc);
        removeDataDir(currentDataDir);
        currentDataDir = createQuotedTempDataDir();
        proc = spawnCloudBackend(backendPort, currentDataDir, cloudServer.url);
        await waitForBackend(backendUrl);
      },
    };

    await use(controller);

    await stopBackendProcess(proc);
    removeDataDir(currentDataDir);
  },
});
