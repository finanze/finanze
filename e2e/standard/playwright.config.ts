import { defineConfig, devices } from "@playwright/test";
import { join } from "node:path";

const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT || 7692);
const FRONTEND_PORT = Number(process.env.E2E_FRONTEND_PORT || 5273);
const FRESH_BACKEND_PORT = 7693;
const FRESH_FRONTEND_PORT = 5274;
const CLOUD_BACKEND_PORT = Number(process.env.E2E_CLOUD_BACKEND_PORT || 7694);
const CLOUD_FRONTEND_PORT = Number(process.env.E2E_CLOUD_FRONTEND_PORT || 5275);
const FRONTEND_APP_DIR = join(
  import.meta.dirname,
  "..",
  "..",
  "frontend",
  "app",
);

export default defineConfig<{}, { backendPort: number }>({
  testDir: "./tests",
  timeout: 60_000,
  retries: 1,
  workers: 1,
  fullyParallel: false,

  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "setup",
      testMatch: /signup\.spec\.ts/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "main",
      testIgnore:
        /signup\.spec\.ts|cloud-restore\.spec\.ts|cloud-backup\.spec\.ts/,
      dependencies: ["setup"],
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "cloud-restore",
      testMatch: /cloud-restore\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        backendPort: FRESH_BACKEND_PORT,
        baseURL: `http://localhost:${FRESH_FRONTEND_PORT}`,
      },
    },
    {
      name: "cloud-backup",
      testMatch: /cloud-backup\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        backendPort: CLOUD_BACKEND_PORT,
        baseURL: `http://localhost:${CLOUD_FRONTEND_PORT}`,
      },
    },
  ],

  webServer: [
    {
      command: `pnpm dev --port ${FRONTEND_PORT}`,
      cwd: FRONTEND_APP_DIR,
      env: {
        ...process.env,
        VITE_BASE_URL: `http://localhost:${BACKEND_PORT}`,
        MOBILE_DEV: "1",
        VITE_E2E_MOCK_LOGIN: "1",
      },
      port: FRONTEND_PORT,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: `pnpm dev --port ${FRESH_FRONTEND_PORT}`,
      cwd: FRONTEND_APP_DIR,
      env: {
        ...process.env,
        VITE_BASE_URL: `http://localhost:${FRESH_BACKEND_PORT}`,
        VITE_SUPABASE_URL: "https://e2e-mock.supabase.co",
        VITE_SUPABASE_PUBLISHABLE_KEY: "e2e-mock-key",
        MOBILE_DEV: "1",
        VITE_E2E_MOCK_LOGIN: "1",
      },
      port: FRESH_FRONTEND_PORT,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: `pnpm dev --port ${CLOUD_FRONTEND_PORT}`,
      cwd: FRONTEND_APP_DIR,
      env: {
        ...process.env,
        VITE_BASE_URL: `http://localhost:${CLOUD_BACKEND_PORT}`,
        VITE_SUPABASE_URL: "https://e2e-mock.supabase.co",
        VITE_SUPABASE_PUBLISHABLE_KEY: "e2e-mock-key",
        MOBILE_DEV: "1",
        VITE_E2E_MOCK_LOGIN: "1",
      },
      port: CLOUD_FRONTEND_PORT,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
