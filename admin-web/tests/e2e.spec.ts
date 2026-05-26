import { expect, test, type Page } from "@playwright/test";

const apiBase = process.env.E2E_API_BASE_URL || "http://localhost:8001";

async function login(page: Page, username: string, password: string) {
  await page.goto("/login");
  await page.locator('input[autocomplete="username"]').fill(username);
  await page.locator('input[autocomplete="current-password"]').fill(password);
  await page.getByRole("button", { name: "登录" }).click();
}

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

  await login(page, username, password);

  await expect(page).toHaveURL(/\/studio\/profile$/);
  await expect(page.getByText("摄影师资料")).toBeVisible();

  await page.getByRole("menuitem", { name: "套餐" }).click();
  await expect(page.locator(".el-card__header").filter({ hasText: "套餐管理" })).toBeVisible();

  const packageName = `E2E 套餐 ${suffix}`;
  await page.locator(".el-form-item").filter({ hasText: "名称" }).locator("input").fill(packageName);
  await page.locator(".el-form-item").filter({ hasText: "价格(元)" }).locator("input").fill("199");
  await page.locator(".el-form-item").filter({ hasText: "时长(分钟)" }).locator("input").fill("30");
  await page.locator(".el-form-item").filter({ hasText: "描述" }).locator("textarea").fill("端到端测试套餐");
  const createPackageRes = page.waitForResponse(
    (res) => res.url().includes("/studio/packages") && res.request().method() === "POST" && res.ok()
  );
  const refreshPackagesRes = page.waitForResponse(
    (res) => res.url().includes("/studio/packages") && res.request().method() === "GET" && res.ok()
  );
  await page.getByRole("button", { name: "新增套餐" }).click();
  await createPackageRes;
  await refreshPackagesRes;

  const row = page.locator(".el-table__row", {
    has: page.getByDisplayValue(packageName)
  });
  await expect(row).toBeVisible({ timeout: 15_000 });

  await row.getByRole("button", { name: "删除" }).click();
  await expect(page.getByDisplayValue(packageName)).toHaveCount(0, { timeout: 15_000 });
});

test("管理员后台：登录后进入审核页并可查看风险管理", async ({ page, request }) => {
  const suffix = Date.now();
  const username = `e2e_admin_${suffix}`;
  const password = "E2e_admin_pass_123456!";
  const photographerName = `e2e_risk_${suffix}`;

  const createAdminRes = await request.post(`${apiBase}/auth/dev/create-admin`, {
    params: { username, password }
  });
  if (!createAdminRes.ok()) {
    throw new Error(`创建管理员失败：${createAdminRes.status()} ${await createAdminRes.text()}`);
  }

  const createPhotographerRes = await request.post(`${apiBase}/auth/dev/create-photographer`, {
    params: { username: photographerName, password: "e2e_photo_pass_123456" }
  });
  if (!createPhotographerRes.ok()) {
    throw new Error(`创建摄影师失败：${createPhotographerRes.status()} ${await createPhotographerRes.text()}`);
  }

  await login(page, username, password);

  await expect(page).toHaveURL(/\/admin\/certifications$/);
  await expect(page.getByText("摄影师认证审核")).toBeVisible();
  await expect(page.getByText("管理员")).toBeVisible();

  await page.getByRole("menuitem", { name: "风险管理" }).click();
  await expect(page).toHaveURL(/\/admin\/risk-users$/);
  await expect(page.getByText("风险标记 / 黑名单")).toBeVisible();

  await page.getByPlaceholder("搜索昵称 / 姓名 / 手机号").fill(photographerName);
  await page.getByRole("button", { name: "搜索" }).click();
  await expect(page.getByText(photographerName)).toBeVisible();
});

test("摄影师访问管理路由时会被重定向回工作台", async ({ page, request }) => {
  const suffix = Date.now();
  const username = `e2e_guard_${suffix}`;
  const password = "e2e_guard_pass_123456";

  const createRes = await request.post(`${apiBase}/auth/dev/create-photographer`, {
    params: { username, password }
  });
  if (!createRes.ok()) {
    throw new Error(`创建摄影师失败：${createRes.status()} ${await createRes.text()}`);
  }

  await login(page, username, password);
  await expect(page).toHaveURL(/\/studio\/profile$/);

  await page.goto("/ops-x8r7m2q4p9/admin/risk-users");
  await expect(page).toHaveURL(/\/studio\/profile$/);
  await expect(page.getByText("当前账号不是管理员，已自动切换到摄影师工作台。")).toBeVisible();
});
