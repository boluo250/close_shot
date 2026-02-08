import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL || "http://localhost:5173";
const apiBase = process.env.E2E_API_BASE_URL || "http://localhost:8001";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  use: {
    baseURL,
    trace: "on-first-retry"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ],
  webServer: {
    command: "npm run dev -- --host 127.0.0.1 --port 5173",
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    env: {
      VITE_API_BASE_URL: apiBase
    }
  }
});
