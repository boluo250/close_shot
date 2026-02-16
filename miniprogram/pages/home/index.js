const theme = require("../../utils/theme");

Page({
  data: {
    activeTab: "nearby",
    theme: "classic",
    themeClass: "cs-theme-classic"
  },

  onLoad(query) {
    // 首次进入：默认汽水风格（如果用户没手动选过）
    try {
      const stored = wx.getStorageSync(theme.STORAGE_KEY);
      if (!stored) theme.setTheme("soda");
    } catch (e) {
      // ignore
    }

    const t = theme.getTheme();
    this.setData({ theme: t, themeClass: theme.getThemeClass(t) });
    this._unsubTheme = theme.subscribe((next) => {
      this.setData({ theme: next, themeClass: theme.getThemeClass(next) });
    });

    const tab = query?.tab;
    if (tab === "favorites" || tab === "mine" || tab === "nearby") {
      this.setData({ activeTab: tab });
    }
  },

  onUnload() {
    if (this._unsubTheme) this._unsubTheme();
  },

  onReady() {
    this._maybeRefreshActive();
  },

  onShow() {
    // 返回/切回时，刷新当前 tab（轻量）
    this._maybeRefreshActive();
  },

  async onPullDownRefresh() {
    await this._maybeRefreshActive(true);
    wx.stopPullDownRefresh();
  },

  onTabTap(e) {
    const tab = e.currentTarget.dataset.tab;
    if (!tab || tab === this.data.activeTab) return;
    this.setData({ activeTab: tab });
    this._maybeRefreshActive();
  },

  onGoFavorites() {
    this.setData({ activeTab: "favorites" });
    this._maybeRefreshActive();
  },

  onThemeChange(e) {
    const next = e?.detail?.value;
    const t = theme.setTheme(next);
    this.setData({ theme: t, themeClass: theme.getThemeClass(t) });
  },

  async _maybeRefreshActive(force = false) {
    const tab = this.data.activeTab;
    if (tab === "nearby") {
      const comp = this.selectComponent("#nearbyPanel");
      if (comp && comp.refresh) return await comp.refresh();
    }
    if (tab === "favorites") {
      const comp = this.selectComponent("#favPanel");
      if (comp && comp.refresh) return await comp.refresh();
    }
    if (tab === "mine") {
      const comp = this.selectComponent("#minePanel");
      if (comp && comp.refresh) return await comp.refresh();
    }
    if (force) {
      // no-op
    }
  }
});

