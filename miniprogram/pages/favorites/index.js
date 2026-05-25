const { request } = require("../../utils/request");

Page({
  data: {
    loading: false,
    list: [],
    themeClass: "cs-theme-soda"
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
