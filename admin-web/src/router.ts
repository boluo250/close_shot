import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "./stores/auth";
import { ADMIN_HOME_PATH, ADMIN_LOGIN_PATH, ADMIN_WEB_BASE } from "./lib/adminSecurity";

import LoginView from "./views/LoginView.vue";
import LayoutView from "./views/LayoutView.vue";
import SeedView from "./views/SeedView.vue";
import StudioProfileView from "./views/StudioProfileView.vue";
import StudioPortfolioView from "./views/StudioPortfolioView.vue";
import StudioPackagesView from "./views/StudioPackagesView.vue";
import StudioUploadView from "./views/StudioUploadView.vue";
import AdminCertificationsView from "./views/AdminCertificationsView.vue";
import AdminAnalyticsView from "./views/AdminAnalyticsView.vue";
import AdminDbView from "./views/AdminDbView.vue";

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
        { path: "admin/analytics", component: AdminAnalyticsView },
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

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.path !== ADMIN_LOGIN_PATH && !auth.token) return ADMIN_LOGIN_PATH;
  if (to.path === ADMIN_LOGIN_PATH && auth.token) return ADMIN_HOME_PATH;
});

