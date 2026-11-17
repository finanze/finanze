import fs from "fs";
import path from "path";
import { expect, type Page } from "@playwright/test";
import { test } from "../../fixtures/cloud-backend";
import { setupSupabaseMockRoutes } from "../../helpers/cloud-backup-mock-server";
import { TEST_PASSWORD } from "../../helpers/constants";
import { navigateToMyMoneyPage } from "../../helpers/my-money";

function ordinal(day: number): string {
  const remainder = day % 100;
  if (remainder >= 11 && remainder <= 13) return `${day}th`;
  switch (day % 10) {
    case 1:
      return `${day}st`;
    case 2:
      return `${day}nd`;
    case 3:
      return `${day}rd`;
    default:
      return `${day}th`;
  }
}

async function selectTodayAsSinceDate(page: Page) {
  const dialog = page.locator(".fixed.inset-0").last();
  const sinceField = dialog
    .locator("label")
    .filter({ hasText: /^Since/ })
    .locator("..");
  await sinceField.getByRole("button").click();

  const calendar = page.locator("[data-radix-popper-content-wrapper]").last();
  await expect(calendar).toBeVisible();

  const today = new Date();
  const targetMonth = new Intl.DateTimeFormat("en-US", {
    month: "long",
    year: "numeric",
  }).format(today);
  await expect(calendar.getByText(targetMonth, { exact: true })).toBeVisible();

  const monthName = new Intl.DateTimeFormat("en-US", {
    month: "long",
  }).format(today);
  const dayName = new RegExp(
    `${monthName}\\s+${ordinal(today.getDate())},\\s+${today.getFullYear()}`,
  );
  const dayCell = calendar.getByRole("gridcell", { name: dayName });
  await expect(dayCell).toBeVisible();
  await dayCell.getByRole("button").click();
}

async function createBudgetExpense(
  page: Page,
  name: string,
  amount: string,
  category: string,
) {
  await navigateToMyMoneyPage(page, "Budget");
  await page.getByRole("tab", { name: /^Expenses/ }).click();
  await page.getByRole("button", { name: "Add", exact: true }).click();
  const dialog = page.locator(".fixed.inset-0").last();
  await dialog.getByPlaceholder("Enter name").fill(name);
  await dialog.getByRole("textbox").nth(1).fill(amount);
  await dialog.getByPlaceholder("Enter category").fill(category);
  await dialog.getByTestId("label-option-groceries").click();
  await selectTodayAsSinceDate(page);
  await dialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
}

async function signUpFreshUser(page: Page, username: string) {
  await page.goto("/");
  await page.locator("#username").waitFor({ timeout: 20_000 });
  await page.fill("#username", username);
  await page.fill("#password", TEST_PASSWORD);
  await page.fill("#repeatPassword", TEST_PASSWORD);
  await page.locator('button[type="submit"]').click();
  await expect(
    page.getByRole("heading", { name: "Summary", exact: true }),
  ).toBeVisible({ timeout: 20_000 });
}

async function openCloudSettings(page: Page) {
  await page.locator('button[aria-label="Settings"]').first().click();
  await page.getByRole("tab", { name: "Cloud" }).click();
}

async function signInToCloudSettings(page: Page, email: string) {
  await openCloudSettings(page);
  await page.locator('input[type="email"]').waitFor({ timeout: 10_000 });
  await page.fill('input[type="email"]', email);
  await page.fill('input[type="password"]', "password123");
  await page.getByRole("button", { name: "Sign in with Email" }).click();
  await expect(
    page.getByRole("button", { name: "Manual", exact: true }),
  ).toBeVisible({ timeout: 15_000 });
}

function listFirstUserDirFiles(dataDir: string): {
  userDir: string | null;
  files: string[];
} {
  const profilesRoot = path.join(dataDir, "profiles");
  if (!fs.existsSync(profilesRoot)) {
    return { userDir: null, files: [] };
  }
  const entries = fs
    .readdirSync(profilesRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory());
  if (entries.length === 0) {
    return { userDir: null, files: [] };
  }
  const userDir = path.join(profilesRoot, entries[0].name);
  return { userDir, files: fs.readdirSync(userDir) };
}

async function logoutAndBackdateLocalRegistry(
  page: Page,
  dataDir: string,
  dateIso: string,
) {
  await page.keyboard.press("Escape");
  await page.locator('button[aria-label="Logout"]').click();
  const confirmLogout = page.locator("button.text-red-500", {
    hasText: "Logout",
  });
  await confirmLogout.waitFor();
  await confirmLogout.click();

  await page.locator("#password").waitFor({ timeout: 10_000 });

  const { userDir } = listFirstUserDirFiles(dataDir);
  expect(userDir).not.toBeNull();
  const cloudJsonPath = path.join(userDir!, "cloud.json");
  const cloudData = JSON.parse(fs.readFileSync(cloudJsonPath, "utf-8")) as {
    backup?: { backups?: { DATA?: { date?: string } } };
  };
  expect(cloudData.backup?.backups?.DATA).toBeDefined();
  cloudData.backup!.backups!.DATA!.date = dateIso;
  fs.writeFileSync(cloudJsonPath, JSON.stringify(cloudData, null, 2));

  await page.fill("#password", TEST_PASSWORD);
  await page.locator('button[type="submit"]').click();
  await expect(
    page.getByRole("heading", { name: "Summary", exact: true }),
  ).toBeVisible({ timeout: 20_000 });
}

async function fetchBackendStatus(
  backendUrl: string,
  page?: Page,
): Promise<{
  status: string;
  lastLogged: string | null;
}> {
  const headers: Record<string, string> = {};
  if (page) {
    const token = await page.evaluate(
      () =>
        window.sessionStorage.getItem("finanze_api_session") ??
        window.localStorage.getItem("finanze_api_session"),
    );
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }
  const res = await fetch(`${backendUrl}/api/v1/status`, { headers });
  expect(res.ok).toBe(true);
  return (await res.json()) as { status: string; lastLogged: string | null };
}

test.describe("Cloud Backup & Restore — Real SQLCipher Point 3 & Version Flows", () => {
  test("logged-in sync preserves local DB and WAL data across Point 3a/3b failures, imports valid remote, and overrides OUTDATED_APP", async ({
    page,
    cloudBackend,
    cloudServer,
  }) => {
    test.setTimeout(120_000);

    await cloudBackend.resetToFreshInstance();
    await setupSupabaseMockRoutes(page, "cloud-e2e@example.com");
    await page.setViewportSize({ width: 1440, height: 1000 });

    await signUpFreshUser(page, "cloud_sync_user");
    await createBudgetExpense(page, "Cloud Saved Rent", "950", "Housing");

    await signInToCloudSettings(page, "cloud-e2e@example.com");
    await page.getByRole("button", { name: "Manual", exact: true }).click();

    const initialSyncBtn = page.getByRole("button", { name: "Sync now" });
    await expect(initialSyncBtn).toBeEnabled({ timeout: 15_000 });
    await initialSyncBtn.click();
    await expect(page.getByText("Synced", { exact: true })).toBeVisible({
      timeout: 30_000,
    });

    const validBackup = cloudServer.getDataPiece();
    expect(validBackup).toBeDefined();
    expect(validBackup!.version).toBeGreaterThanOrEqual(120005);

    const twentyMinutesAgo = new Date(Date.now() - 20 * 60_000).toISOString();
    const tenMinutesAgo = new Date(Date.now() - 10 * 60_000).toISOString();
    const agedValidBackup = cloudServer.createBackdatedBackupPiece({
      piece: validBackup!,
      password: TEST_PASSWORD,
      date: tenMinutesAgo,
    });

    await logoutAndBackdateLocalRegistry(
      page,
      cloudBackend.dataDir,
      twentyMinutesAgo,
    );

    await createBudgetExpense(
      page,
      "Local Unprotected Sub",
      "29",
      "Subscriptions",
    );

    // KO 1a: Point 3a — remote backup has ahead-of-time DB migration (without version header)
    await cloudServer.mutateDataPieceWithPython({
      basePayload: validBackup!.payload,
      password: TEST_PASSWORD,
      mode: "ahead_of_time",
    });

    await openCloudSettings(page);
    const conflictSyncBtn = page.getByRole("button", { name: "Sync now" });
    await expect(conflictSyncBtn).toBeEnabled({ timeout: 15_000 });
    await conflictSyncBtn.click();

    await expect(page.getByText("Conflict detected")).toBeVisible({
      timeout: 15_000,
    });
    await page.getByRole("button", { name: "Use remote" }).click();

    await expect(
      page.getByText(
        "Backup was created with a newer version of Finanze. Please update the app.",
      ),
    ).toBeVisible({ timeout: 30_000 });

    const after3aFiles = listFirstUserDirFiles(cloudBackend.dataDir);
    expect(after3aFiles.files).toContain("data.db");
    expect(after3aFiles.files).not.toContain("data.db.tmp");
    expect(
      (await fetchBackendStatus(cloudBackend.backendUrl, page)).status,
    ).toBe("UNLOCKED");

    await navigateToMyMoneyPage(page, "Budget");
    await page.getByRole("tab", { name: /^Expenses/ }).click();
    await expect(
      page.getByRole("heading", { name: "Cloud Saved Rent", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", {
        name: "Local Unprotected Sub",
        exact: true,
      }),
    ).toBeVisible();

    // KO 1b: Point 3b — mid-upgrade failure after data.db swap triggers .tmp rollback
    await cloudServer.mutateDataPieceWithPython({
      basePayload: validBackup!.payload,
      password: TEST_PASSWORD,
      mode: "mid_upgrade_failure",
    });

    await openCloudSettings(page);
    await expect(page.getByText("Conflict detected")).toBeVisible({
      timeout: 15_000,
    });
    await page.getByRole("button", { name: "Use remote" }).click();

    await expect(page.getByText("Unexpected error occurred")).toBeVisible({
      timeout: 30_000,
    });

    const after3bFiles = listFirstUserDirFiles(cloudBackend.dataDir);
    expect(after3bFiles.files).toContain("data.db");
    expect(after3bFiles.files).not.toContain("data.db.tmp");
    expect(
      fs.statSync(path.join(after3bFiles.userDir!, "data.db")).size,
    ).toBeGreaterThan(0);
    expect(
      (await fetchBackendStatus(cloudBackend.backendUrl, page)).status,
    ).toBe("UNLOCKED");

    await navigateToMyMoneyPage(page, "Budget");
    await page.getByRole("tab", { name: /^Expenses/ }).click();
    await expect(
      page.getByRole("heading", { name: "Cloud Saved Rent", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", {
        name: "Local Unprotected Sub",
        exact: true,
      }),
    ).toBeVisible();

    // OK 1c: Valid remote backup force-imports cleanly and overwrites local-only changes
    await cloudServer.restoreDataPieceAsNewer(agedValidBackup, {
      date: tenMinutesAgo,
    });

    await openCloudSettings(page);
    await expect(page.getByText("Conflict detected")).toBeVisible({
      timeout: 15_000,
    });
    await page.getByRole("button", { name: "Use remote" }).click();
    await expect(page.getByText("Synced", { exact: true })).toBeVisible({
      timeout: 30_000,
    });
    expect(listFirstUserDirFiles(cloudBackend.dataDir).files).not.toContain(
      "data.db.tmp",
    );

    await navigateToMyMoneyPage(page, "Budget");
    await page.getByRole("tab", { name: /^Expenses/ }).click();
    await expect(
      page.getByRole("heading", { name: "Cloud Saved Rent", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", {
        name: "Local Unprotected Sub",
        exact: true,
      }),
    ).toHaveCount(0);

    // KO + OK 1d: Remote XYYZZMM version > local reports OUTDATED_APP, disables Use remote, allows Use local override
    await cloudServer.restoreDataPieceAsNewer(validBackup!, {
      version: 130001,
    });

    await openCloudSettings(page);
    const outdatedSyncBtn = page.getByRole("button", { name: "Sync now" });
    await expect(outdatedSyncBtn).toBeEnabled({ timeout: 15_000 });
    await outdatedSyncBtn.click();

    await expect(
      page.getByText("Update required", { exact: true }),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByText("Newer backup version (v0.13.0)"),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Use remote" }),
    ).toBeDisabled();

    const useLocalBtn = page.getByRole("button", { name: "Use local" });
    await expect(useLocalBtn).toBeEnabled();
    await useLocalBtn.click();

    await expect(page.getByText("Synced", { exact: true })).toBeVisible({
      timeout: 30_000,
    });
    expect(cloudServer.getDataPiece()?.version).toBe(validBackup!.version);
  });

  test("onboarding Cloud Restore cleans up broken DB files, stays LOCKED across Point 3 failures, and restores valid backup", async ({
    page,
    browser,
    cloudBackend,
    cloudServer,
  }) => {
    test.setTimeout(120_000);

    await cloudBackend.resetToFreshInstance();
    await setupSupabaseMockRoutes(page, "restore-e2e@example.com");
    await page.setViewportSize({ width: 1440, height: 1000 });

    await signUpFreshUser(page, "seed_backup_user");
    await createBudgetExpense(page, "Restored Rent", "1200", "Housing");

    await signInToCloudSettings(page, "restore-e2e@example.com");
    await page.getByRole("button", { name: "Manual", exact: true }).click();

    const seedSyncBtn = page.getByRole("button", { name: "Sync now" });
    await expect(seedSyncBtn).toBeEnabled({ timeout: 15_000 });
    await seedSyncBtn.click();
    await expect(page.getByText("Synced", { exact: true })).toBeVisible({
      timeout: 30_000,
    });

    const seededBackup = cloudServer.getDataPiece();
    expect(seededBackup).toBeDefined();

    await page.close();
    await cloudBackend.resetToFreshInstance();

    const restoreContext = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
    });
    const restorePage = await restoreContext.newPage();
    try {
      await setupSupabaseMockRoutes(restorePage, "restore-e2e@example.com");
      await restorePage.goto("/");
      await restorePage
        .getByText("Have a Cloud account? Restore your data")
        .waitFor({ timeout: 20_000 });
      await restorePage
        .getByText("Have a Cloud account? Restore your data")
        .click();

      await restorePage
        .locator('input[type="email"]')
        .waitFor({ timeout: 10_000 });
      await restorePage.fill('input[type="email"]', "restore-e2e@example.com");
      await restorePage.fill('input[type="password"]', "password123");
      await restorePage
        .getByRole("button", { name: "Sign in with Email" })
        .click();

      await expect(restorePage.getByText("Backup found!")).toBeVisible({
        timeout: 15_000,
      });

      // KO 2a: Wrong encryption key
      await restorePage.fill("#restoreUsername", "restored_user");
      await restorePage.fill("#encryptionKey", "WrongKey999!");
      await restorePage
        .getByRole("button", { name: "Restore", exact: true })
        .click();

      await expect(
        restorePage.getByText(
          "Invalid encryption key. Please check and try again.",
        ),
      ).toBeVisible({ timeout: 30_000 });
      expect(listFirstUserDirFiles(cloudBackend.dataDir).files).not.toContain(
        "data.db",
      );
      expect(
        (await fetchBackendStatus(cloudBackend.backendUrl, restorePage)).status,
      ).toBe("LOCKED");

      // KO 2b: Point 3a — ahead-of-time migration rejected before creating data.db
      await cloudServer.mutateDataPieceWithPython({
        basePayload: seededBackup!.payload,
        password: TEST_PASSWORD,
        mode: "ahead_of_time",
      });

      await restorePage.fill("#encryptionKey", TEST_PASSWORD);
      await restorePage
        .getByRole("button", { name: "Restore", exact: true })
        .click();

      await expect(
        restorePage.getByText(
          "This backup was created with a newer version of Finanze. Please update the app to restore it.",
        ),
      ).toBeVisible({ timeout: 30_000 });

      const after2bFiles = listFirstUserDirFiles(cloudBackend.dataDir).files;
      expect(after2bFiles).not.toContain("data.db");
      expect(after2bFiles).not.toContain("data.db.tmp");
      expect(
        (await fetchBackendStatus(cloudBackend.backendUrl, restorePage)).status,
      ).toBe("LOCKED");

      // KO 2c: Point 3b — mid-upgrade failure deletes broken data.db/-wal/-shm and leaves backend LOCKED
      await cloudServer.mutateDataPieceWithPython({
        basePayload: seededBackup!.payload,
        password: TEST_PASSWORD,
        mode: "mid_upgrade_failure",
      });

      await restorePage
        .getByRole("button", { name: "Restore", exact: true })
        .click();

      await expect(
        restorePage.getByText("Restore failed. Please try again."),
      ).toBeVisible({ timeout: 30_000 });

      const after2cFiles = listFirstUserDirFiles(cloudBackend.dataDir).files;
      expect(after2cFiles).not.toContain("data.db");
      expect(after2cFiles).not.toContain("data.db-wal");
      expect(after2cFiles).not.toContain("data.db-shm");
      expect(after2cFiles).not.toContain("data.db.tmp");
      expect(
        (await fetchBackendStatus(cloudBackend.backendUrl, restorePage)).status,
      ).toBe("LOCKED");

      // OK 2d: Valid backup restores cleanly end-to-end and unlocks restored SQLCipher data
      await cloudServer.restoreDataPieceAsNewer(seededBackup!);

      await restorePage
        .getByRole("button", { name: "Restore", exact: true })
        .click();

      await expect(
        restorePage.getByRole("heading", { name: "Summary", exact: true }),
      ).toBeVisible({
        timeout: 30_000,
      });

      const restoredFiles = listFirstUserDirFiles(cloudBackend.dataDir).files;
      expect(restoredFiles).toContain("data.db");
      expect(restoredFiles).not.toContain("data.db.tmp");

      await navigateToMyMoneyPage(restorePage, "Budget");
      await restorePage.getByRole("tab", { name: /^Expenses/ }).click();
      await expect(
        restorePage.getByRole("heading", {
          name: "Restored Rent",
          exact: true,
        }),
      ).toBeVisible();
    } finally {
      await restoreContext.close();
    }
  });
});
