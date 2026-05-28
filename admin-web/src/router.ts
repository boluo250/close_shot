import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "./stores/auth";
import { ADMIN_HOME_PATH, ADMIN_LOGIN_PATH, ADMIN_WEB_BASE, STUDIO_HOME_PATH } from "./lib/adminSecurity";
import { fetchMyIdentity, resolveHomePath } from "./lib/authIdentity";

import LoginView from "./views/LoginView.vue";
import LayoutView from "./views/LayoutView.vue";
import SeedView from "./views/SeedView.vue";
import StudioProfileView from "./views/StudioProfileView.vue";
import StudioPortfolioView from "./views/StudioPortfolioView.vue";
import StudioPackagesView from "./views/StudioPackagesView.vue";
import StudioUploadView from "./views/StudioUploadView.vue";
import AdminCertificationsView from "./views/AdminCertificationsView.vue";
import AdminRiskUsersView from "./views/AdminRiskUsersView.vue";
import AdminAnalyticsView from "./views/AdminAnalyticsView.vue";
import AdminDbView from "./views/AdminDbView.vue";
import AdminAppointmentsView from "./views/AdminAppointmentsView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: ADMIN_LOGIN_PATH, component: LoginView },
    {
      path: ADMIN_WEB_BASE,
      component: LayoutView,
      children: [
        { path: "", redirect: ADMIN_HOME_PATH },
        { path: "seed", component: SeedView },
        { path: "studio/upload", component: StudioUploadView },
        { path: "studio/profile", component: StudioProfileView },
        { path: "studio/portfolio", component: StudioPortfolioView },
        { path: "studio/packages", component: StudioPackagesView },
        { path: "admin/certifications", component: AdminCertificationsView },
        { path: "admin/risk-users", component: AdminRiskUsersView },
        { path: "admin/analytics", component: AdminAnalyticsView },
        { path: "admin/appointments", component: AdminAppointmentsView },
        {
          path: "admin/system-monitor",
          component: () => import("./views/AdminSystemMonitorView.vue")
        },
        { path: "admin/db", component: AdminDbView },
        {
          path: "admin/user-portraits",
          component: () => import("./views/AdminUserPortraitsView.vue")
        },
        {
          path: "admin/operation-logs",
          component: () => import("./views/AdminOperationLogsView.vue")
        }
      ]
    },
    { path: "/", redirect: ADMIN_LOGIN_PATH },
    { path: "/:pathMatch(.*)*", redirect: ADMIN_LOGIN_PATH }
  ]
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (to.path !== ADMIN_LOGIN_PATH && !auth.token) return ADMIN_LOGIN_PATH;

  if (!auth.token) return;

  if (!auth.identity) {
    try {
      auth.setIdentity(await fetchMyIdentity());
    } catch {
      auth.logout();
      return ADMIN_LOGIN_PATH;
    }
  }

  const role = auth.identity?.role || "";
  const isAdminRoute = to.path.startsWith(`${ADMIN_WEB_BASE}/admin`) || to.path === `${ADMIN_WEB_BASE}/seed`;
  const isStudioRoute = to.path.startsWith(`${ADMIN_WEB_BASE}/studio`);

  if (to.path === ADMIN_LOGIN_PATH) return resolveHomePath(auth.identity);
  if (isAdminRoute && role !== "admin") return role === "photographer" ? STUDIO_HOME_PATH : ADMIN_LOGIN_PATH;
  if (isStudioRoute && role !== "photographer") return role === "admin" ? ADMIN_HOME_PATH : ADMIN_LOGIN_PATH;
});
