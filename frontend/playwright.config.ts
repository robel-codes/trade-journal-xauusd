import { defineConfig } from "@playwright/test";

// Runs against a live stack (API on :8000, web on :3000). See README "End-to-end tests".
export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000", viewport: { width: 1680, height: 1000 }, colorScheme: "dark",
    // Optional: use a pre-installed Chromium instead of Playwright's download.
    launchOptions: process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {} },
  reporter: [["list"]],
});
