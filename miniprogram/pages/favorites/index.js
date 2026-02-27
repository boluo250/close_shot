const { request } = require("../../utils/request");
const theme = require("../../utils/theme");

Page({
  data: {
    loading: false,
    list: [],
    theme: "classic",
    themeClass: "cs-theme-classic"
  },

  onLoad() {
    const t = theme.getTheme();
    this.setData({ theme: t, themeClass: theme.getThemeClass(t) });
    this._unsubTheme = theme.subscribe((next) => {
      this.setData({ theme: next, themeClass: theme.getThemeClass(next) });
    });
  },

  onUnload() {
    if (this._unsubTheme) this._unsubTheme();
  },

  async onShow() {
    await this.refresh();
  },

  async refresh() {
    this.setData({ loading: true });
    try {
      const list = await request("/me/favorites", { auth: true });
      this.setData({ list: list || [] });
    } catch (e) {
      const msg = e?.message || "";
      const needLogin = msg.includes("Missing bearer token") || msg.includes("Invalid token");
      wx.showToast({ title: needLogin ? "请先登录" : "加载失败，请稍后重试", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/photographer/index?id=${id}` });
  }
});

