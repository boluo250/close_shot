const theme = require("./utils/theme");
const env = require("./env");

function resolveApiBaseUrl() {
  // 优先使用 env 中配置的线上地址，确保默认直连部署后端
  if (env.API_BASE_URL) {
    return env.API_BASE_URL.replace(/\/+$/, "");
  }

  return `http://${env.DEV_API_HOST}:${env.DEV_API_PORT}`;
}

App({
  globalData: {
    apiBaseUrl: resolveApiBaseUrl(),
    theme: "classic"
  },
  onLaunch() {
    const t = theme.getTheme();
    this.globalData.theme = t;
    theme.applySystemUI(t);
  }
});

