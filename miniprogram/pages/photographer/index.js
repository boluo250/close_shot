const { request } = require("../../utils/request");

Page({
  data: {
    id: null,
    p: {},
    portfolio: [],
    packages: [],
    ratingText: "-",
    fav: false
  },

  async onLoad(query) {
    const id = Number(query.id);
    this.setData({ id });
    await this.load();
  },

  async load() {
    try {
      const app = getApp();
      const base = app.globalData.apiBaseUrl;
      const data = await request(`/photographers/${this.data.id}`);
      // 若后端返回相对路径（/media/...），小程序补全为完整 URL
      if (Array.isArray(data.portfolio_items)) {
        data.portfolio_items = data.portfolio_items.map((x) => ({
          ...x,
          image_url: x.image_url && x.image_url.startsWith("/") ? base + x.image_url : x.image_url
        }));
      }
      const ratingText =
        data.rating_count > 0 ? `${data.rating_avg.toFixed(1)}（${data.rating_count}）` : "-";

      // WXML 表达式不支持方法调用（如 toFixed），这里先把价格格式化好
      const packages = Array.isArray(data.packages)
        ? data.packages.map((x) => ({
            ...x,
            price_yuan:
              typeof x.price_cents === "number" ? (x.price_cents / 100).toFixed(0) : ""
          }))
        : [];

      this.setData({
        p: data,
        portfolio: data.portfolio_items || [],
        packages,
        ratingText
      });
    } catch (e) {
      wx.showToast({ title: "加载失败", icon: "none" });
    }
  },

  async toggleFav() {
    try {
      if (this.data.fav) {
        await request(`/photographers/${this.data.id}/favorite`, { method: "DELETE", auth: true });
        this.setData({ fav: false });
      } else {
        await request(`/photographers/${this.data.id}/favorite`, { method: "POST", auth: true });
        this.setData({ fav: true });
      }
      wx.showToast({ title: "已更新", icon: "none" });
    } catch (e) {
      wx.showToast({ title: "操作失败", icon: "none" });
    }
  },

  contact() {
    wx.showModal({
      title: "提示",
      content: "这里后续可接：拨打电话/加微信/留资 Lead。",
      showCancel: false
    });
  }
});

