const { request } = require("../../utils/request");

Page({
  data: {
    id: null,
    p: {},
    portfolio: [],
    packages: [],
    rateCard: [],
    equipmentList: [],
    droneModels: [],
    reviews: [],
    reviewsLoading: false,
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
      const rateCard = Array.isArray(data.rate_card)
        ? data.rate_card.map((x) => ({
            ...x,
            price_yuan:
              typeof x.price_cents === "number" ? (x.price_cents / 100).toFixed(0) : "",
            mode_label: x.mode === "hour" ? "按小时" : "按件"
          }))
        : [];
      const equipmentList = Array.isArray(data.equipment_list) ? data.equipment_list : [];
      const droneModels = Array.isArray(data.drone_models) ? data.drone_models : [];

      this.setData({
        p: data,
        portfolio: data.portfolio_items || [],
        packages,
        rateCard,
        equipmentList,
        droneModels,
        ratingText
      });
      await this.loadReviews();
    } catch (e) {
      wx.showToast({ title: "加载失败", icon: "none" });
    }
  },

  async loadReviews() {
    this.setData({ reviewsLoading: true });
    try {
      const list = await request(`/photographers/${this.data.id}/reviews`, {
        params: { limit: 20 }
      });
      const reviews = Array.isArray(list)
        ? list.map((x) => ({
            ...x,
            display_name: x.user_display_name || "匿名客户",
            avatar_url: x.user_avatar_url || "",
            created_date: x.created_at ? String(x.created_at).slice(0, 10) : "",
            star_text: "⭐".repeat(Math.max(1, Math.min(5, Number(x.rating) || 0)))
          }))
        : [];
      this.setData({ reviews });
    } catch (e) {
      this.setData({ reviews: [] });
    } finally {
      this.setData({ reviewsLoading: false });
    }
  },

  previewPortfolio(e) {
    const idx = Number(e.currentTarget.dataset.idx || 0);
    const urls = (this.data.portfolio || []).map((x) => x.image_url).filter(Boolean);
    if (!urls.length) return;
    wx.previewImage({ current: urls[idx] || urls[0], urls });
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

