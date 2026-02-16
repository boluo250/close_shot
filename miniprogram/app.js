const theme = require("./utils/theme");

App({
  globalData: {
    // 本地后端端口（开发机跑在 8001 时同步修改这里）
    apiBaseUrl: "http://localhost:8001",
    theme: "classic"
  },
  onLaunch() {
    const t = theme.getTheme();
    this.globalData.theme = t;
    theme.applySystemUI(t);
  }
});

