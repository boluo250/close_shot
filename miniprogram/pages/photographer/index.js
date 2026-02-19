const { request } = require("../../utils/request");
const theme = require("../../utils/theme");

Page({
  data: {
    id: null,
    p: {},
    portfolio: [],
    packages: [],
    rateCard: [],
    offerings: [],
    equipmentList: [],
    droneModels: [],
    hasEquipment: false,
    serviceRadiusKm: 0,
    fav: false,
    theme: "classic",
    themeClass: "cs-theme-classic"
  },

  async onLoad(query) {
    const t = theme.getTheme();
    this.setData({ theme: t, themeClass: theme.getThemeClass(t) });
    this._unsubTheme = theme.subscribe((next) => {
      this.setData({ theme: next, themeClass: theme.getThemeClass(next) });
    });

    const id = Number(query.id);
    this.setData({ id });
    await this.load();
  },

  onUnload() {
    if (this._unsubTheme) this._unsubTheme();
  },

  onThemeChange(e) {
    const next = e?.detail?.value;
    const t = theme.setTheme(next);
    this.setData({ theme: t, themeClass: theme.getThemeClass(t) });
  },

  async load() {
    try {
      const app = getApp();
      const base = app.globalData.apiBaseUrl;
      const data = await request(`/photographers/${this.data.id}`);
      // 补全图片URL
      if (Array.isArray(data.portfolio_items)) {
        data.portfolio_items = data.portfolio_items.map((x) => ({
          ...x,
          image_url: x.image_url && x.image_url.startsWith("/") ? base + x.image_url : x.image_url
        }));
      }

      // 套餐格式化
      const packages = Array.isArray(data.packages)
        ? data.packages
            .filter((x) => x.is_active)
            .map((x) => ({
              ...x,
              price_yuan:
                typeof x.price_cents === "number" ? (x.price_cents / 100).toFixed(0) : ""
            }))
        : [];

      // 报价单格式化
      const rateCard = Array.isArray(data.rate_card)
        ? data.rate_card.map((x) => ({
            ...x,
            price_yuan:
              typeof x.price_cents === "number" ? (x.price_cents / 100).toFixed(0) : "",
            mode_label: x.mode === "hour" ? "按小时" : "按张数"
          }))
        : [];

      // 合并展示列表（不改变后端结构，仅用于详情页 UI）
      const offerings = [
        ...packages.map((x) => ({
          key: `pkg-${x.id}`,
          type: "package",
          name: x.name,
          price_yuan: x.price_yuan,
          meta: x.duration_minutes ? `${x.duration_minutes} 分钟` : "",
          description: x.description || "",
          badge: "套餐"
        })),
        ...rateCard.map((x, idx) => ({
          key: `rate-${idx}-${x.name || "item"}`,
          type: "rate",
          name: x.name,
          price_yuan: x.price_yuan,
          meta: `${x.mode_label}${x.unit ? ` · 单位：${x.unit}` : ""}`,
          description: "",
          badge: x.mode_label
        }))
      ];

      const equipmentList = Array.isArray(data.equipment_list) ? data.equipment_list : [];
      const droneModels = Array.isArray(data.drone_models) ? data.drone_models : [];
      const hasEquipment = equipmentList.length > 0 || droneModels.length > 0;

      // 服务范围 km
      const serviceRadiusKm = data.service_radius_m
        ? Math.round(data.service_radius_m / 1000)
        : 0;

      this.setData({
        p: data,
        portfolio: data.portfolio_items || [],
        packages,
        rateCard,
        offerings,
        equipmentList,
        droneModels,
        hasEquipment,
        serviceRadiusKm,
      });
    } catch (e) {
      wx.showToast({ title: "加载失败", icon: "none" });
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
      title: "联系摄影师",
      content: "可通过拨打电话或添加微信联系摄影师，功能即将上线。",
      showCancel: false
    });
  }
});
