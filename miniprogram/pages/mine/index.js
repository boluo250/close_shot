const { getToken, setToken, ensureLogin } = require("../../utils/auth");

Page({
  data: {
    token: "",
    loading: false
  },

  onShow() {
    const tab = this.getTabBar && this.getTabBar();
    if (tab && tab.setData) tab.setData({ selected: 2 });
    this.refresh();
  },

  refresh() {
    this.setData({ token: getToken() || "" });
  },

  async login() {
    this.setData({ loading: true });
    try {
      const t = await ensureLogin();
      this.setData({ token: t || "" });
      wx.showToast({ title: "已登录", icon: "none" });
    } catch (e) {
      wx.showToast({ title: "登录失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },

  logout() {
    setToken("");
    this.setData({ token: "" });
    wx.showToast({ title: "已退出", icon: "none" });
  },

  goFavorites() {
    wx.switchTab({ url: "/pages/favorites/index" });
  },

  goStudio() {
    wx.navigateTo({ url: "/pages/studio/index" });
  }
});

