import { expect, test } from "@playwright/test";

const apiBase = process.env.E2E_API_BASE_URL || "http://localhost:8001";

test("摄影师后台：登录与套餐 CRUD", async ({ page, request }) => {
  const suffix = Date.now();
  const username = `e2e_photographer_${suffix}`;
  const password = "e2e_pass_123456";

  const createRes = await request.post(`${apiBase}/auth/dev/create-photographer`, {
    params: { username, password }
  });
  if (!createRes.ok()) {
    throw new Error(`创建摄影师失败：${createRes.status()} ${await createRes.text()}`);
  }

  await page.goto("/login");
  await page.locator('input[autocomplete="username"]').fill(username);
  await page.locator('input[autocomplete="current-password"]').fill(password);
  await page.getByRole("button", { name: "登录" }).click();

  await expect(page).toHaveURL(/\/studio\/profile$/);
  await expect(page.getByText("摄影师资料")).toBeVisible();

  await page.getByRole("menuitem", { name: "套餐" }).click();
  await expect(page.getByText("套餐管理")).toBeVisible();

  const packageName = `E2E 套餐 ${suffix}`;
  await page.locator(".el-form-item").filter({ hasText: "名称" }).locator("input").fill(packageName);
  await page.locator(".el-form-item").filter({ hasText: "价格(元)" }).locator("input").fill("199");
  await page.locator(".el-form-item").filter({ hasText: "时长(分钟)" }).locator("input").fill("30");
  await page.locator(".el-form-item").filter({ hasText: "描述" }).locator("textarea").fill("端到端测试套餐");
  await page.getByRole("button", { name: "新增套餐" }).click();

  const row = page.locator("tr").filter({ hasText: packageName });
  await expect(row).toBeVisible();

  await row.getByRole("button", { name: "删除" }).click();
  await expect(row).toHaveCount(0);
});
