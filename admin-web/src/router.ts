import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "./stores/auth";

import LoginView from "./views/LoginView.vue";
import LayoutView from "./views/LayoutView.vue";
import SeedView from "./views/SeedView.vue";
import StudioProfileView from "./views/StudioProfileView.vue";
import StudioPortfolioView from "./views/StudioPortfolioView.vue";
import StudioPackagesView from "./views/StudioPackagesView.vue";
import AdminCertificationsView from "./views/AdminCertificationsView.vue";
import AdminAnalyticsView from "./views/AdminAnalyticsView.vue";
import AdminDbView from "./views/AdminDbView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: LoginView },
    {
      path: "/",
      component: LayoutView,
      children: [
        { path: "", redirect: "/studio/profile" },
        { path: "seed", component: SeedView },
        { path: "studio/profile", component: StudioProfileView },
        { path: "studio/portfolio", component: StudioPortfolioView },
        { path: "studio/packages", component: StudioPackagesView },
        { path: "admin/certifications", component: AdminCertificationsView },
        { path: "admin/analytics", component: AdminAnalyticsView },
        { path: "admin/db", component: AdminDbView }
      ]
    }
  ]
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.path !== "/login" && !auth.token) return "/login";
  if (to.path === "/login" && auth.token) return "/";
});

