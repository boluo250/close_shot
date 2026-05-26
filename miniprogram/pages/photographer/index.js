const { request } = require("../../utils/request");
const { getToken, ensureLogin } = require("../../utils/auth");

Page({
  data: {
    id: null,
    distanceText: "",
    fromSource: "",
    p: {},
    bioExpanded: false,
    bioCanExpand: false,
    portfolio: [],
    packages: [],
    rateCard: [],
    offerings: [],
    equipmentList: [],
    droneModels: [],
    hasEquipment: false,
    serviceRadiusKm: 0,
    fav: false,
    canViewContact: false,
    contactAccessMode: "all",
    contactLockReason: "",
    isOwnerPhotographer: false,
    themeClass: "cs-theme-soda"
  },

  async onLoad(query) {
    const id = Number(query.id);
    this.setData({
      id,
      distanceText: decodeURIComponent(query.distance || ""),
      fromSource: decodeURIComponent(query.from || "")
    });
    await this.load();
  },

  async load() {
    try {
      const app = getApp();
      const base = app.globalData.apiBaseUrl;
      const data = await request(`/photographers/${this.data.id}`, { auth: !!getToken() });
      data.avatar_url =
        data.avatar_url && data.avatar_url.startsWith("/") ? base + data.avatar_url : data.avatar_url;
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
        bioExpanded: false,
        bioCanExpand: false,
        portfolio: data.portfolio_items || [],
        packages,
        rateCard,
        offerings,
        equipmentList,
        droneModels,
        hasEquipment,
        serviceRadiusKm,
        fav: !!data.is_favorited,
        canViewContact: !!data.can_view_contact,
        contactAccessMode: data.contact_access_mode || "all",
        contactLockReason: data.contact_lock_reason || "",
      });
      wx.nextTick(() => this.measureBioOverflow());
      await this.checkOwnerEditable(data);
    } catch (e) {
      wx.showToast({ title: "加载失败", icon: "none" });
    }
  },

  async checkOwnerEditable(detailData) {
    try {
      const identity = await request("/me/identity", { auth: true });
      if (!identity || !["photographer", "admin"].includes(identity.role)) {
        this.setData({ isOwnerPhotographer: false });
        return;
      }
      if (identity.role === "photographer" && identity.photographer_status !== "approved") {
        this.setData({ isOwnerPhotographer: false });
        return;
      }
      const meStudio = await request("/studio/me", { auth: true });
      const myPhotographerId = meStudio?.photographer?.id;
      this.setData({ isOwnerPhotographer: Number(myPhotographerId) === Number(detailData?.id) });
    } catch (_e) {
      this.setData({ isOwnerPhotographer: false });
    }
  },

  previewPortfolio(e) {
    const idx = Number(e.currentTarget.dataset.idx || 0);
    const urls = (this.data.portfolio || []).map((x) => x.image_url).filter(Boolean);
    if (!urls.length) return;
    wx.previewImage({ current: urls[idx] || urls[0], urls });
  },

  previewAvatar() {
    const avatarUrl = this.data.p?.avatar_url;
    if (!avatarUrl) return;
    wx.previewImage({ current: avatarUrl, urls: [avatarUrl] });
  },

  toggleBioExpanded() {
    this.setData({ bioExpanded: !this.data.bioExpanded });
  },

  measureBioOverflow() {
    if (!this.data.p?.bio) {
      if (this.data.bioCanExpand) {
        this.setData({ bioCanExpand: false });
      }
      return;
    }
    const query = wx.createSelectorQuery();
    query.select("#p-bio-collapsed").boundingClientRect();
    query.select("#p-bio-full").boundingClientRect();
    query.exec((res) => {
      const [collapsedRect, fullRect] = res || [];
      const canExpand =
        !!collapsedRect &&
        !!fullRect &&
        typeof collapsedRect.height === "number" &&
        typeof fullRect.height === "number" &&
        fullRect.height - collapsedRect.height > 8;
      if (canExpand !== this.data.bioCanExpand) {
        this.setData({ bioCanExpand: canExpand });
      }
    });
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

  async contact() {
    if (!this.data.canViewContact) {
      if (this.data.contactLockReason === "login_required") {
        try {
          await ensureLogin();
          await this.load();
          if (!this.data.canViewContact) {
            wx.showToast({ title: "请开通会员后查看", icon: "none" });
            return;
          }
        } catch (_e) {
          wx.showToast({ title: "登录失败", icon: "none" });
          return;
        }
      } else {
        wx.showModal({
          title: "会员可见",
          content: "开通会员后可查看摄影师联系方式，会员功能即将上线。",
          showCancel: false
        });
        return;
      }
    }

    const phone = this.data.p?.phone || "";
    const wechat = this.data.p?.wechat_id || "";
    if (!phone && !wechat) {
      wx.showToast({ title: "摄影师暂未填写联系方式", icon: "none" });
      return;
    }

    const actions = [];
    if (phone) actions.push("拨打电话");
    if (wechat) actions.push("复制微信号");
    actions.push("查看联系方式");
    wx.showActionSheet({
      itemList: actions,
      success: ({ tapIndex }) => {
        const key = actions[tapIndex];
        if (key === "拨打电话") {
          wx.makePhoneCall({ phoneNumber: phone });
          return;
        }
        if (key === "复制微信号") {
          wx.setClipboardData({
            data: wechat,
            success: () => wx.showToast({ title: "微信号已复制", icon: "none" })
          });
          return;
        }
        wx.showModal({
          title: "联系方式",
          content: `电话：${phone || "未填写"}\n微信：${wechat || "未填写"}`,
          showCancel: false
        });
      }
    });
  },

  goEditProfile() {
    wx.navigateTo({ url: "/pages/studio/index" });
  }
});
