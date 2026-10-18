import { expect, test } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";

const EMAIL = process.env.E2E_EMAIL ?? "trader@example.com";
const PASSWORD = process.env.E2E_PASSWORD ?? "e2e-password-123";
const FIX = path.resolve(__dirname, "../../backend/tests/fixtures/pine");
const SHOTS = process.env.E2E_SHOTS;

async function shot(page: import("@playwright/test").Page, name: string) {
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true });
}

test("sign in, import a ZIP of scripts, inspect a compatibility report", async ({ page }, info) => {
  await page.goto("/strategies");
  await expect(page).toHaveURL(/\/login\?next=%2Fstrategies/);
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Email or password is incorrect.")).toBeVisible();
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Strategy Library" })).toBeVisible();

  // Build a zip of the fixtures plus a junk file, the way a TradingView export folder might look.
  const zip = path.join(info.outputDir, "pack.zip");
  fs.mkdirSync(info.outputDir, { recursive: true });
  execFileSync("python3", ["-c", `import zipfile,sys,os
z=zipfile.ZipFile(sys.argv[1],'w')
for f in sorted(os.listdir(sys.argv[2])): z.write(os.path.join(sys.argv[2],f), 'xau/'+f)
z.writestr('xau/notes.docx','x')`, zip, FIX]);

  // Fresh database: the library is empty, so the import panel is open by default.
  await expect(page.getByText("No scripts yet")).toBeVisible();
  await expect(page.getByText("Drop .pine, .txt or .zip")).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles(zip);
  await page.getByRole("button", { name: /^Import 1 file/ }).click();
  await expect(page.getByText("Import report")).toBeVisible();
  const report = page.locator("table").first();
  await expect(report).toContainText("notes.docx");
  await expect(report).toContainText("Unsupported file type .docx");
  await shot(page, "01-import-report");

  // Library table shows the classification for each script
  const table = page.locator("table").last();
  await expect(table).toContainText("XAU EMA Cross ATR");
  await expect(table.getByRole("row", { name: /HTF Bias Leak/ })).toContainText("Manual conversion");
  await expect(table.getByRole("row", { name: /RSI Zones/ })).toContainText("Not executable");

  // Re-importing the same archive is detected as duplicate, nothing new is created
  await page.locator('input[type="file"]').setInputFiles(zip);
  await page.getByRole("button", { name: /^Import 1 file/ }).click();
  await expect(page.getByText(/duplicate/).first()).toBeVisible();

  await table.getByRole("row", { name: /HTF Bias Leak/ }).click();
  await expect(page.getByRole("heading", { name: "HTF Bias Leak" })).toBeVisible();
  await expect(page.getByText("Lookahead without offset (future data)")).toBeVisible();
  await shot(page, "02-compatibility");

  // Jump from a finding to the source line
  await page.getByRole("listitem").filter({ hasText: "Lookahead without offset" }).getByRole("button", { name: "line 3" }).click();
  await expect(page.locator('[data-line="3"]')).toContainText("lookahead_on");
  await shot(page, "03-source");

  await page.getByRole("tab", { name: /Details/ }).click();
  await page.getByLabel("Trading hypothesis").fill("Daily bias filter; expected to fail out of sample because of lookahead.");
  await page.getByRole("button", { name: "Save" }).click();
  await expect(page.getByRole("status")).toHaveText("Saved.");
});

test("overview shows honest empty states, theme toggles", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill(EMAIL);
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Overview" })).toBeVisible();
  await expect(page.getByText("No closed trades yet").first()).toBeVisible();
  await expect(page.getByText("No backtests yet")).toBeVisible();
  await expect(page.getByText("scripts analyzed").or(page.getByText("No strategies imported"))).toBeVisible();
  await shot(page, "04-overview-dark");
  await page.getByRole("button", { name: "Toggle light or dark theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await shot(page, "05-overview-light");
  await page.getByRole("button", { name: "Toggle light or dark theme" }).click();
  await expect(page.locator("html")).not.toHaveAttribute("data-theme", "light");
});
