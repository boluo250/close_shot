Page({
  data: {
    activeTab: "nearby",
    themeClass: "cs-theme-soda"
  },

  onLoad(query) {
    // 首页固定为汽水风格
    this.setData({ themeClass: "cs-theme-soda" });

    const tab = query?.tab;
    if (tab === "favorites" || tab === "mine" || tab === "nearby") {
      this.setData({ activeTab: tab });
    }
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

