const { request } = require("../../../utils/request");
const { ensureLogin } = require("../../../utils/auth");
const { uploadImageToS3Like } = require("../../../utils/upload");

const PRICE_RANGES = ["199-399", "399-699", "699+"];

Page({
  data: {
    step: 1,        // 当前步骤 1-3
    totalSteps: 3,
    submitting: false,

    // Step 1: 实名认证
    realName: "",
    idCardNumber: "",

    // Step 2: 资料完善（选填，但会在详情页展示）
    portfolioLink: "",
    avatarUrl: "",
    avatarObjectKey: "",
    bio: "",
    bioTemplates: [],
    equipmentItems: [],
    newEquipment: "",
    droneItems: [],
    newDrone: "",
    portfolioDraft: [], // [{ image_url, image_object_key }]
    portfolioUploading: false,
    portfolioUploadCount: 0,
    packagesDraft: [], // [{ name, price_yuan, duration_minutes, description, is_active }]
    newPackage: { name: "", price_yuan: "", duration_minutes: "", description: "", is_active: true },
    rateCardDraft: [], // [{ name, mode: hour/photo, price_yuan, unit }]
    newRateItem: { name: "", mode: "hour", price_yuan: "", unit: "" },
    offeringsDraft: [], // UI 合并展示用
    newOffering: {
      kind: "package", // package/hour/photo
      name: "",
      price_yuan: "",
      duration_minutes: "",
      description: "",
      is_active: true,
      unit: ""
    },

    // Step 3: 联系方式
    phone: "",
    wechatId: "",

    // 可选
    city: "",
    priceRanges: PRICE_RANGES,
    priceRangeIndex: -1,
    priceRange: "",
    serviceCenterLat: null,
    serviceCenterLng: null,
    serviceRadiusM: 5000,
    locationText: "未设置",

    // 表单校验
    step1Valid: false,
    step2Valid: true,
    step3Valid: false,
  },

  onLoad() {
    // 尝试获取手机号自动填充
    this._loadCertificationStatus();
    this.loadBioTemplates();
    this._rebuildOfferingsDraft();
  },

  async _loadCertificationStatus() {
    try {
      await ensureLogin();
      const res = await request("/me/photographer/certification", { method: "GET", auth: true });
      const isSubmissionComplete = !!(res.identity_verified && res.contact_verified && res.portfolio_uploaded);
      // 只有资料完整且已提交审核时，才直接跳转审核页；否则允许继续补资料/补传作品
      if (res.status === "pending" && isSubmissionComplete) {
        wx.redirectTo({ url: "/pages/auth/review/index" });
        return;
      }
      if (res.status === "pending") {
        wx.showToast({ title: "资料未完整，可继续补充后重提", icon: "none" });
      }
      // 如果已通过认证，跳转工作台
      if (res.status === "approved") {
        wx.showToast({ title: "你已通过认证", icon: "none" });
        wx.reLaunch({ url: "/pages/home/index?tab=mine" });
        return;
      }
    } catch (e) {
      // 未申请过，正常显示认证表单
    }
  },

  // ========== Step 1: 实名认证 ==========
  onRealNameInput(e) {
    this.setData({ realName: e.detail.value });
    this._validateStep1();
  },

  onIdCardInput(e) {
    this.setData({ idCardNumber: e.detail.value });
    this._validateStep1();
  },

  _validateStep1() {
    const { realName, idCardNumber } = this.data;
    const valid = realName.length >= 2 && this._isValidIdCard(idCardNumber);
    this.setData({ step1Valid: valid });
  },

  _isValidIdCard(num) {
    return /^\d{15}$|^\d{17}[\dXx]$/.test(num);
  },

  onPortfolioLinkInput(e) {
    this.setData({ portfolioLink: e.detail.value });
  },

  // ========== Step 2: 基础资料/设备/作品/套餐/报价 ==========
  onBioInput(e) {
    this.setData({ bio: e.detail.value });
  },

  async loadBioTemplates() {
    try {
      const items = await request("/me/bio-templates", { method: "GET", auth: true });
      if (Array.isArray(items) && items.length > 0) {
        this.setData({ bioTemplates: items.slice(0, 3) });
        return;
      }
    } catch (e) {
      // ignore and fallback
    }
    this.setData({
      bioTemplates: [
        "善于捕捉自然光影的记录者，偏爱真实与松弛的氛围。",
        "喜欢用镜头讲故事，擅长把情绪拍进画面里。",
        "温柔系摄影师，擅长引导，让你自然好看。"
      ]
    });
  },

  useBioTemplate(e) {
    const tpl = e.currentTarget.dataset.tpl;
    if (!tpl) return;
    this.setData({ bio: tpl });
  },

  async chooseAvatar() {
    const choose = await new Promise((resolve) => {
      wx.chooseMedia({
        count: 1,
        mediaType: ["image"],
        sourceType: ["album", "camera"],
        success: resolve,
        fail: () => resolve(null)
      });
    });
    const file = choose?.tempFiles?.[0];
    if (!file) return;
    try {
      const up = await uploadImageToS3Like({
        tempFilePath: file.tempFilePath,
        filename: file.tempFilePath.split("/").pop() || "avatar.jpg",
        contentType: file.fileType ? `image/${file.fileType}` : "image/jpeg",
        prefix: "avatar"
      });
      const app = getApp();
      const base = app.globalData.apiBaseUrl;
      const imageUrl = (up.proxy_url ? base + up.proxy_url : "") || up.public_url || "";
      if (!up.object_key) throw new Error("no object key");
      this.setData({ avatarUrl: imageUrl || "", avatarObjectKey: up.object_key || "" });
    } catch (e) {
      wx.showToast({ title: (e && e.message) || "头像上传失败", icon: "none" });
    }
  },

  onNewEquipment(e) {
    this.setData({ newEquipment: e.detail.value });
  },
  addEquipment() {
    const val = (this.data.newEquipment || "").trim();
    if (!val) return;
    if (this.data.equipmentItems.includes(val)) {
      wx.showToast({ title: "已存在", icon: "none" });
      return;
    }
    this.setData({ equipmentItems: [...this.data.equipmentItems, val], newEquipment: "" });
  },
  removeEquipment(e) {
    const idx = Number(e.currentTarget.dataset.index);
    const items = [...this.data.equipmentItems];
    items.splice(idx, 1);
    this.setData({ equipmentItems: items });
  },

  onNewDrone(e) {
    this.setData({ newDrone: e.detail.value });
  },
  addDrone() {
    const val = (this.data.newDrone || "").trim();
    if (!val) return;
    if (this.data.droneItems.includes(val)) {
      wx.showToast({ title: "已存在", icon: "none" });
      return;
    }
    this.setData({ droneItems: [...this.data.droneItems, val], newDrone: "" });
  },
  removeDrone(e) {
    const idx = Number(e.currentTarget.dataset.index);
    const items = [...this.data.droneItems];
    items.splice(idx, 1);
    this.setData({ droneItems: items });
  },

  async choosePortfolioDraft() {
    if (this.data.portfolioUploading) return;
    const choose = await new Promise((resolve) => {
      wx.chooseMedia({
        count: 9,
        mediaType: ["image"],
        sourceType: ["album", "camera"],
        success: resolve,
        fail: () => resolve(null)
      });
    });
    const files = choose?.tempFiles || [];
    if (!files.length) return;

    this.setData({ portfolioUploading: true, portfolioUploadCount: files.length });
    try {
      const ups = await Promise.all(
        files.map(async (file) => {
          const up = await uploadImageToS3Like({
            tempFilePath: file.tempFilePath,
            filename: file.tempFilePath.split("/").pop() || "portfolio.jpg",
            contentType: file.fileType ? `image/${file.fileType}` : "image/jpeg",
            prefix: "portfolio"
          });
          if (!up.object_key) throw new Error("no object key");
          const app = getApp();
          const base = app.globalData.apiBaseUrl;
          const imageUrl = (up.proxy_url ? base + up.proxy_url : "") || up.public_url || "";
          return { image_url: imageUrl || "", image_object_key: up.object_key || null };
        })
      );
      this.setData({ portfolioDraft: [...this.data.portfolioDraft, ...ups] });
    } catch (e) {
      wx.showToast({ title: (e && e.message) || "作品上传失败", icon: "none" });
    } finally {
      this.setData({ portfolioUploading: false, portfolioUploadCount: 0 });
    }
  },

  previewPortfolioDraft(e) {
    const idx = Number(e.currentTarget.dataset.idx || 0);
    const urls = (this.data.portfolioDraft || []).map((x) => x.image_url).filter(Boolean);
    if (!urls.length) return;
    wx.previewImage({ current: urls[idx] || urls[0], urls });
  },

  removePortfolioDraft(e) {
    const idx = Number(e.currentTarget.dataset.index);
    const items = [...this.data.portfolioDraft];
    items.splice(idx, 1);
    this.setData({ portfolioDraft: items });
  },

  _rebuildOfferingsDraft() {
    const offerings = [
      ...(this.data.packagesDraft || []).map((x, i) => ({
        key: `pkg-${i}-${x.name || ""}`,
        source: "package",
        sourceIndex: i,
        name: x.name,
        badge: "套餐",
        sub: `¥${x.price_yuan || "-"}${x.duration_minutes ? ` · ${x.duration_minutes}分钟` : ""}`
      })),
      ...(this.data.rateCardDraft || []).map((x, i) => ({
        key: `rate-${i}-${x.name || ""}`,
        source: "rate",
        sourceIndex: i,
        name: x.name,
        badge: x.mode === "photo" ? "按张数" : "按小时",
        sub: `¥${x.price_yuan || "-"} / ${x.mode === "photo" ? "张" : "小时"}${x.unit ? ` · ${x.unit}` : ""}`
      }))
    ];
    this.setData({ offeringsDraft: offerings });
  },

  onNewOfferingField(e) {
    const field = e.currentTarget.dataset.field;
    const value = e.detail.value;
    this.setData({ [`newOffering.${field}`]: value });
  },

  onOfferingKindChange(e) {
    const idx = Number(e.detail.value);
    const kinds = ["package", "hour", "photo"];
    const next = kinds[idx] || "package";
    this.setData({ "newOffering.kind": next });
  },

  toggleNewOfferingActive(e) {
    this.setData({ "newOffering.is_active": !!e.detail.value });
  },

  addOfferingDraft() {
    const o = this.data.newOffering || {};
    const kind = o.kind || "package";
    const name = (o.name || "").trim();
    const price = (o.price_yuan || "").trim();
    if (!name) {
      wx.showToast({ title: "请填写名称", icon: "none" });
      return;
    }
    if (kind !== "package" && !price) {
      wx.showToast({ title: "请填写价格", icon: "none" });
      return;
    }

    if (kind === "package") {
      const pkg = {
        name,
        price_yuan: price,
        duration_minutes: (o.duration_minutes || "").trim(),
        description: (o.description || "").trim(),
        is_active: !!o.is_active
      };
      this.setData(
        {
          packagesDraft: [...this.data.packagesDraft, pkg],
          newOffering: {
            kind: "package",
            name: "",
            price_yuan: "",
            duration_minutes: "",
            description: "",
            is_active: true,
            unit: ""
          }
        },
        () => this._rebuildOfferingsDraft()
      );
      return;
    }

    const rate = {
      name,
      mode: kind === "photo" ? "photo" : "hour",
      price_yuan: price,
      unit: (o.unit || "").trim()
    };
    this.setData(
      {
        rateCardDraft: [...this.data.rateCardDraft, rate],
        newOffering: {
          kind,
          name: "",
          price_yuan: "",
          duration_minutes: "",
          description: "",
          is_active: true,
          unit: ""
        }
      },
      () => this._rebuildOfferingsDraft()
    );
  },

  removeOfferingDraft(e) {
    const source = e.currentTarget.dataset.source;
    const idx = Number(e.currentTarget.dataset.index);
    if (source === "package") {
      const items = [...this.data.packagesDraft];
      items.splice(idx, 1);
      this.setData({ packagesDraft: items }, () => this._rebuildOfferingsDraft());
      return;
    }
    const items = [...this.data.rateCardDraft];
    items.splice(idx, 1);
    this.setData({ rateCardDraft: items }, () => this._rebuildOfferingsDraft());
  },

  onNewPackageField(e) {
    const field = e.currentTarget.dataset.field;
    const value = e.detail.value;
    this.setData({ [`newPackage.${field}`]: value });
  },
  toggleNewPackageActive(e) {
    this.setData({ "newPackage.is_active": !!e.detail.value });
  },
  addPackageDraft() {
    const p = this.data.newPackage || {};
    const name = (p.name || "").trim();
    if (!name) {
      wx.showToast({ title: "请填写套餐名称", icon: "none" });
      return;
    }
    this.setData({
      packagesDraft: [...this.data.packagesDraft, { ...p, name }],
      newPackage: { name: "", price_yuan: "", duration_minutes: "", description: "", is_active: true }
    }, () => this._rebuildOfferingsDraft());
  },
  removePackageDraft(e) {
    const idx = Number(e.currentTarget.dataset.index);
    const items = [...this.data.packagesDraft];
    items.splice(idx, 1);
    this.setData({ packagesDraft: items }, () => this._rebuildOfferingsDraft());
  },

  onNewRateField(e) {
    const field = e.currentTarget.dataset.field;
    const value = e.detail.value;
    this.setData({ [`newRateItem.${field}`]: value });
  },
  onNewRateModeChange(e) {
    const idx = Number(e.detail.value);
    const modes = ["hour", "photo"];
    this.setData({ "newRateItem.mode": modes[idx] || "hour" });
  },
  addRateItemDraft() {
    const it = this.data.newRateItem || {};
    const name = (it.name || "").trim();
    const price = (it.price_yuan || "").trim();
    if (!name || !price) {
      wx.showToast({ title: "请填写报价名称与价格", icon: "none" });
      return;
    }
    this.setData({
      rateCardDraft: [
        ...this.data.rateCardDraft,
        { name, mode: it.mode || "hour", price_yuan: price, unit: (it.unit || "").trim() }
      ],
      newRateItem: { name: "", mode: "hour", price_yuan: "", unit: "" }
    }, () => this._rebuildOfferingsDraft());
  },
  removeRateItemDraft(e) {
    const idx = Number(e.currentTarget.dataset.index);
    const items = [...this.data.rateCardDraft];
    items.splice(idx, 1);
    this.setData({ rateCardDraft: items }, () => this._rebuildOfferingsDraft());
  },

  _validateStep2() {},

  // ========== Step 3: 联系方式 ==========
  onPhoneInput(e) {
    this.setData({ phone: e.detail.value });
    this._validateStep3();
  },

  onWechatInput(e) {
    this.setData({ wechatId: e.detail.value });
    this._validateStep3();
  },

  onCityInput(e) {
    this.setData({ city: e.detail.value });
  },

  onPriceRangeChange(e) {
    const idx = Number(e.detail.value);
    this.setData({
      priceRangeIndex: idx,
      priceRange: PRICE_RANGES[idx],
    });
  },

  async _getLocationOnce() {
    return await new Promise((resolve, reject) => {
      wx.getLocation({
        type: "gcj02",
        success: resolve,
        fail: reject
      });
    });
  },

  _isLocationAuthError(e) {
    const msg = String(e?.errMsg || "").toLowerCase();
    return (
      msg.includes("auth deny") ||
      msg.includes("auth denied") ||
      msg.includes("permission denied")
    );
  },

  _formatLocationError(e) {
    const msg = String(e?.errMsg || "");
    if (!msg) return "定位失败，请稍后重试";
    if (this._isLocationAuthError(e)) return "定位未授权，请开启位置信息权限";
    if (msg.includes("timeout")) return "定位超时，请到开阔区域重试";
    return `定位失败：${msg}`;
  },

  async _requestLocationPermission() {
    const setting = await new Promise((resolve) => {
      wx.getSetting({
        success: resolve,
        fail: () => resolve({})
      });
    });
    const current = setting?.authSetting?.["scope.userLocation"];

    if (current === true) return true;

    // 首次授权时，直接触发授权弹窗。
    if (current === undefined) {
      try {
        await new Promise((resolve, reject) => {
          wx.authorize({
            scope: "scope.userLocation",
            success: resolve,
            fail: reject
          });
        });
        return true;
      } catch (_e) {
        // 用户在首次授权弹窗里拒绝，继续走 openSetting 引导。
      }
    }

    const modal = await new Promise((resolve) => {
      wx.showModal({
        title: "需要位置信息权限",
        content: "用于设置你的服务位置，是否前往设置开启？",
        confirmText: "去开启",
        cancelText: "暂不",
        success: resolve,
        fail: () => resolve({ confirm: false })
      });
    });
    if (!modal?.confirm) return false;

    const openRes = await new Promise((resolve) => {
      wx.openSetting({
        success: resolve,
        fail: () => resolve({})
      });
    });
    return !!openRes?.authSetting?.["scope.userLocation"];
  },

  async refreshLocation() {
    try {
      const loc = await this._getLocationOnce();
      const lat = Number(loc.latitude);
      const lng = Number(loc.longitude);
      this.setData({
        serviceCenterLat: lat,
        serviceCenterLng: lng,
        locationText: `已定位 ${lat.toFixed(4)}, ${lng.toFixed(4)}`
      });
      wx.showToast({ title: "位置已刷新", icon: "none" });
    } catch (e) {
      if (!this._isLocationAuthError(e)) {
        wx.showToast({ title: this._formatLocationError(e).slice(0, 18), icon: "none" });
        return;
      }

      const granted = await this._requestLocationPermission();
      if (!granted) {
        wx.showToast({ title: "未开启定位权限", icon: "none" });
        return;
      }

      try {
        const loc = await this._getLocationOnce();
        const lat = Number(loc.latitude);
        const lng = Number(loc.longitude);
        this.setData({
          serviceCenterLat: lat,
          serviceCenterLng: lng,
          locationText: `已定位 ${lat.toFixed(4)}, ${lng.toFixed(4)}`
        });
        wx.showToast({ title: "位置已刷新", icon: "none" });
      } catch (e2) {
        wx.showToast({ title: this._formatLocationError(e2).slice(0, 18), icon: "none" });
      }
    }
  },

  _validateStep3() {
    const { phone, wechatId } = this.data;
    const valid = /^1\d{10}$/.test(phone) && wechatId.length > 0;
    this.setData({ step3Valid: valid });
  },

  // ========== 步骤导航 ==========
  nextStep() {
    const { step } = this.data;
    if (step === 1 && !this.data.step1Valid) {
      wx.showToast({ title: "请完善实名认证信息", icon: "none" });
      return;
    }
    if (step < 3) {
      this.setData({ step: step + 1 });
    }
  },

  prevStep() {
    const { step } = this.data;
    if (step > 1) {
      this.setData({ step: step - 1 });
    }
  },

  // ========== 提交认证 ==========
  async submitApply() {
    if (this.data.submitting) return;

    if (!this.data.step3Valid) {
      wx.showToast({ title: "请填写联系方式", icon: "none" });
      return;
    }

    this.setData({ submitting: true });
    let stage = "apply";
    try {
      await ensureLogin();
      const data = {
        real_name: this.data.realName,
        id_card_number: this.data.idCardNumber,
        portfolio_link: this.data.portfolioLink || null,
        phone: this.data.phone,
        wechat_id: this.data.wechatId,
        city: this.data.city || null,
        price_range: this.data.priceRange || null,
        service_center_lat: this.data.serviceCenterLat,
        service_center_lng: this.data.serviceCenterLng,
        service_radius_m: this.data.serviceRadiusM || 5000,
      };
      // 1) 先提交认证（会在后端把用户角色提升为 photographer）
      await request("/me/photographer/apply", { method: "POST", data, auth: true });

      // 2) 写入会在详情页展示的资料（选填）
      stage = "profile";
      const profilePayload = {
        avatar_object_key: this.data.avatarObjectKey || null,
        avatar_url: this.data.avatarUrl || null,
        bio: this.data.bio || null,
        // 标签能力已移除：这里显式清空，避免历史数据残留
        tags: "",
        equipment_list: (this.data.equipmentItems || []).join(","),
        drone_models: (this.data.droneItems || []).join(","),
        rate_card: (this.data.rateCardDraft || []).map((x) => ({
          name: (x.name || "").trim(),
          mode: x.mode === "photo" || x.mode === "item" ? "photo" : "hour",
          price_cents: Math.round(parseFloat(x.price_yuan || "0") * 100),
          unit: (x.unit || "").trim() || null
        }))
      };
      await request("/studio/me", { method: "PUT", data: profilePayload, auth: true });

      // 3) 作品集：提交已上传的草稿
      stage = "portfolio";
      for (const it of this.data.portfolioDraft || []) {
        await request("/studio/portfolio", {
          method: "POST",
          data: {
            title: "",
            tags: "",
            category: "",
            is_pinned: false,
            sort_order: 0,
            image_object_key: it.image_object_key || null
          },
          auth: true
        });
      }

      // 4) 套餐（选填）
      stage = "packages";
      for (const pkg of this.data.packagesDraft || []) {
        const priceValue = parseFloat(pkg.price_yuan || "0");
        const durationVal = pkg.duration_minutes ? parseInt(pkg.duration_minutes, 10) : null;
        await request("/studio/packages", {
          method: "POST",
          data: {
            name: (pkg.name || "").trim(),
            price_cents: Math.round((Number.isNaN(priceValue) ? 0 : priceValue) * 100),
            duration_minutes: Number.isNaN(durationVal) ? null : durationVal,
            description: pkg.description || "",
            is_active: !!pkg.is_active
          },
          auth: true
        });
      }

      wx.showToast({ title: "已提交，等待审核", icon: "none" });
      wx.redirectTo({ url: "/pages/auth/review/index" });
    } catch (e) {
      const stageLabelMap = {
        apply: "认证信息",
        profile: "个人资料",
        portfolio: "作品图片",
        packages: "服务套餐"
      };
      const rawMessage = (e && e.message) || "";
      if (rawMessage.includes("content security check failed")) {
        wx.showToast({
          title: `${stageLabelMap[stage] || "提交内容"}未通过安全校验`,
          icon: "none"
        });
        return;
      }
      wx.showToast({
        title: rawMessage || `${stageLabelMap[stage] || "提交"}保存失败，请稍后重试`,
        icon: "none"
      });
    } finally {
      this.setData({ submitting: false });
    }
  },

  onBackMine() {
    wx.reLaunch({ url: "/pages/home/index?tab=mine" });
  },
});
