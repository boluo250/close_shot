const theme = require("./utils/theme");
const env = require("./env");

function resolveApiBaseUrl() {
  // 允许通过 storage 临时覆盖，便于不同网络快速切换
  const customApiBaseUrl = wx.getStorageSync("apiBaseUrl");
  if (customApiBaseUrl) {
    return customApiBaseUrl;
  }

  // 优先使用内网穿透地址（Cloudflare Tunnel）
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

