const { request } = require("../../utils/request");

Page({
  data: {
    loading: false,
    list: []
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
      wx.showToast({ title: "加载失败（需要登录）", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/photographer/index?id=${id}` });
  }
});

