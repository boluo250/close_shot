const { request } = require("../../utils/request");
const { ensureLogin } = require("../../utils/auth");
const { uploadImageToS3Like } = require("../../utils/upload");
const theme = require("../../utils/theme");

function pad(n) {
  return String(n).padStart(2, "0");
}
function formatDate(y, m, d) {
  return `${y}-${pad(m)}-${pad(d)}`;
}
function buildCalendar(year, month, scheduleMap) {
  const firstDay = new Date(year, month - 1, 1).getDay();
  const daysInMonth = new Date(year, month, 0).getDate();
  const cells = [];
  for (let i = 0; i < firstDay; i += 1) {
    cells.push({ day: "", date: "", status: "" });
  }
  for (let d = 1; d <= daysInMonth; d += 1) {
    const dateStr = formatDate(year, month, d);
    cells.push({ day: d, date: dateStr, status: scheduleMap[dateStr] || "" });
  }
  return cells;
}

// 草稿存储 key
const DRAFT_KEY = "studio_draft_v1";

Page({
  data: {
    token: "",
    authorized: false,
    checkingIdentity: false,
    profileSaving: false,
    portfolioLoading: false,
    portfolioUploading: false,
    portfolioUploadCount: 0,
    packagesLoading: false,
    scheduleLoading: false,
    lastUrl: "",

    // 简介模板（后端随机返回 3 条）
    bioTemplates: [],

    profile: {
      bio: "",
      tags: "",
      avatar_url: "",
      cover_url: ""
    },
    avatarObjectKey: "",
    coverObjectKey: "",
    profileTagOptions: ["日系", "复古", "法式", "胶片", "纪实", "清新", "高级感", "森系", "人像", "氛围感"],
    profileTagSelected: [],

    // 设备清单 & 无人机
    equipmentItems: [],
    newEquipment: "",
    droneItems: [],
    newDrone: "",

    items: [],

    // 预设套餐模板
    presetPackages: [
      { name: "标准人像", price_yuan: "299", duration_minutes: "60", desc: "1小时 / 精修15张", description: "含1小时拍摄、精修15张底片全送" },
      { name: "情侣写真", price_yuan: "499", duration_minutes: "90", desc: "1.5小时 / 精修20张", description: "含1.5小时拍摄、精修20张底片全送" },
      { name: "半日跟拍", price_yuan: "899", duration_minutes: "240", desc: "4小时 / 精修40张", description: "含4小时跟拍、精修40张底片全送" }
    ],

    packages: [],
    showNewPackage: false,
    newPackage: {
      name: "",
      price_yuan: "",
      duration_minutes: "",
      description: "",
      is_active: true
    },

    scheduleExpanded: false,
    scheduleYear: new Date().getFullYear(),
    scheduleMonth: new Date().getMonth() + 1,
    scheduleCells: [],
    scheduleMap: {},

    theme: "classic",
    themeClass: "cs-theme-classic"
  },

  onLoad() {
    const t = theme.getTheme();
    this.setData({ theme: t, themeClass: theme.getThemeClass(t) });
    this._unsubTheme = theme.subscribe((next) => {
      this.setData({ theme: next, themeClass: theme.getThemeClass(next) });
    });

    this.restoreDraft();
    this.checkAndEnter();
  },

  onUnload() {
    if (this._unsubTheme) this._unsubTheme();
    this.saveDraft();
  },

  onThemeChange(e) {
    const next = e?.detail?.value;
    const t = theme.setTheme(next);
    this.setData({ theme: t, themeClass: theme.getThemeClass(t) });
  },

  onHide() {
    this.saveDraft();
  },

  // ============ 草稿箱 ============

  saveDraft() {
    try {
      const draft = {
        bio: this.data.profile.bio,
        tags: this.data.profileTagSelected,
        newPackage: this.data.newPackage
      };
      wx.setStorageSync(DRAFT_KEY, JSON.stringify(draft));
    } catch (e) {
      // ignore
    }
  },

  restoreDraft() {
    try {
      const raw = wx.getStorageSync(DRAFT_KEY);
      if (!raw) return;
      const draft = JSON.parse(raw);
      if (draft.bio && !this.data.profile.bio) {
        this.setData({ "profile.bio": draft.bio });
      }
      if (Array.isArray(draft.tags) && draft.tags.length > 0) {
        this.setData({ profileTagSelected: draft.tags });
      }
      if (draft.newPackage && draft.newPackage.name) {
        this.setData({ newPackage: draft.newPackage, showNewPackage: true });
      }
    } catch (e) {
      // ignore
    }
  },

  clearDraft() {
    try {
      wx.removeStorageSync(DRAFT_KEY);
    } catch (e) {
      // ignore
    }
  },

  // ============ 身份验证 ============

  async checkAndEnter() {
    this.setData({ checkingIdentity: true });
    try {
      const t = await ensureLogin();
      const identity = await request("/me/identity", { auth: true });
      const status = identity.photographer_status;
      const isApproved = identity.role === "admin" || status === "approved";
      if (!isApproved) {
        const reason = identity.photographer_reject_reason || "";
        if (status === "pending") {
          wx.redirectTo({ url: "/pages/auth/review/index" });
        } else if (status === "rejected") {
          wx.redirectTo({
            url: `/pages/auth/rejected/index?reason=${encodeURIComponent(reason)}`
          });
        } else {
          wx.redirectTo({ url: "/pages/auth/apply/index" });
        }
        return;
      }
      this.setData({ token: t || "", authorized: true });
      await this.refreshAll();
    } catch (e) {
      wx.showToast({ title: "身份校验失败", icon: "none" });
      wx.reLaunch({ url: "/pages/mine/index" });
    } finally {
      this.setData({ checkingIdentity: false });
    }
  },

  async studioRequest(path, { method = "GET", data = null, params = null } = {}) {
    const app = getApp();
    const base = app.globalData.apiBaseUrl;
    const url = params
      ? base +
        path +
        "?" +
        Object.keys(params)
          .filter((k) => params[k] !== undefined && params[k] !== null && params[k] !== "")
          .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
          .join("&")
      : base + path;

    return await new Promise((resolve, reject) => {
      wx.request({
        url,
        method,
        data,
        header: { Authorization: "Bearer " + this.data.token },
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) resolve(res.data);
          else reject(new Error(res.data?.detail || "request failed"));
        },
        fail: reject
      });
    });
  },

  // ============ 个人资料 ============

  onBio(e) {
    this.setData({ "profile.bio": e.detail.value });
  },

  useBioTemplate(e) {
    const tpl = e.currentTarget.dataset.tpl;
    this.setData({ "profile.bio": tpl });
  },

  toggleProfileTag(e) {
    const tag = e.currentTarget.dataset.tag;
    const selected = new Set(this.data.profileTagSelected);
    if (selected.has(tag)) selected.delete(tag);
    else selected.add(tag);
    this.setData({ profileTagSelected: Array.from(selected) });
  },

  // ============ 设备清单 ============

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
    this.setData({
      equipmentItems: [...this.data.equipmentItems, val],
      newEquipment: ""
    });
  },

  removeEquipment(e) {
    const idx = e.currentTarget.dataset.index;
    const items = [...this.data.equipmentItems];
    items.splice(idx, 1);
    this.setData({ equipmentItems: items });
  },

  // ============ 无人机 ============

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
    this.setData({
      droneItems: [...this.data.droneItems, val],
      newDrone: ""
    });
  },

  removeDrone(e) {
    const idx = e.currentTarget.dataset.index;
    const items = [...this.data.droneItems];
    items.splice(idx, 1);
    this.setData({ droneItems: items });
  },

  async refreshAll() {
    if (!this.data.token) return;
    await Promise.all([
      this.loadBioTemplates(),
      this.loadProfile(),
      this.loadPortfolio(),
      this.loadPackages(),
      this.loadSchedule()
    ]);
  },

  async loadBioTemplates() {
    try {
      const items = await request("/me/bio-templates", { auth: true });
      if (Array.isArray(items) && items.length > 0) {
        this.setData({ bioTemplates: items.slice(0, 3) });
        return;
      }
    } catch (e) {
      // ignore and fallback
    }
    // fallback（后端未部署/无数据时）
    this.setData({
      bioTemplates: [
        "善于捕捉自然光影的记录者，偏爱真实与松弛的氛围。",
        "喜欢用镜头讲故事，擅长把情绪拍进画面里。",
        "温柔系摄影师，擅长引导，让你自然好看。"
      ]
    });
  },

  async loadProfile() {
    if (!this.data.token) return;
    try {
      const data = await this.studioRequest("/studio/me");
      const profile = data.photographer || {};
      const selected = (profile.tags || "")
        .split(",")
        .map((t) => t.trim())
        .filter((t) => t);
      // 解析设备清单和无人机（后端返回为 list）
      const equipmentItems = Array.isArray(profile.equipment_list)
        ? profile.equipment_list
        : (profile.equipment_list || "").split(",").map((s) => s.trim()).filter((s) => s);
      const droneItems = Array.isArray(profile.drone_models)
        ? profile.drone_models
        : (profile.drone_models || "").split(",").map((s) => s.trim()).filter((s) => s);
      this.setData({
        profile: {
          bio: profile.bio || "",
          tags: profile.tags || "",
          avatar_url: profile.avatar_url || "",
          cover_url: profile.cover_url || ""
        },
        profileTagSelected: selected.length > 0 ? selected : this.data.profileTagSelected,
        equipmentItems,
        droneItems
      });
    } catch (e) {
      wx.showToast({ title: "加载资料失败", icon: "none" });
    }
  },

  async saveProfile() {
    if (!this.data.token) return;
    this.setData({ profileSaving: true });
    try {
      const tags = this.data.profileTagSelected.join(",");
      const payload = {
        bio: this.data.profile.bio,
        tags,
        avatar_url: this.data.profile.avatar_url,
        avatar_object_key: this.data.avatarObjectKey || null,
        cover_url: this.data.profile.cover_url,
        cover_object_key: this.data.coverObjectKey || null,
        equipment_list: this.data.equipmentItems.join(","),
        drone_models: this.data.droneItems.join(",")
      };
      await this.studioRequest("/studio/me", { method: "PUT", data: payload });
      this.setData({ "profile.tags": tags, avatarObjectKey: "", coverObjectKey: "" });
      this.clearDraft();
      wx.showToast({ title: "资料已保存", icon: "none" });
    } catch (e) {
      wx.showToast({ title: "资料保存失败", icon: "none" });
    } finally {
      this.setData({ profileSaving: false });
    }
  },

  async maybeCrop(src) {
    if (typeof wx.cropImage !== "function") return src;
    const res = await new Promise((resolve) => {
      wx.cropImage({
        src,
        success: (r) => resolve(r.tempFilePath || src),
        fail: () => resolve(src)
      });
    });
    return res;
  },

  async chooseProfileImage(e) {
    const type = e.currentTarget.dataset.type;
    if (!this.data.token) {
      wx.showToast({ title: "请先登录", icon: "none" });
      return;
    }
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
      const croppedPath = await this.maybeCrop(file.tempFilePath);
      const up = await uploadImageToS3Like({
        tempFilePath: croppedPath,
        filename: croppedPath.split("/").pop() || "image.jpg",
        contentType: file.fileType ? `image/${file.fileType}` : "image/jpeg",
        prefix: type === "avatar" ? "avatar" : "cover"
      });
      const app = getApp();
      const base = app.globalData.apiBaseUrl;
      const imageUrl = up.public_url || (up.proxy_url ? base + up.proxy_url : "");
      if (!imageUrl) throw new Error("no url");
      if (type === "avatar") {
        this.setData({ "profile.avatar_url": imageUrl, avatarObjectKey: up.object_key || "" });
      } else {
        this.setData({ "profile.cover_url": imageUrl, coverObjectKey: up.object_key || "" });
      }
      await this.saveProfile();
    } catch (e) {
      wx.showToast({ title: "上传失败", icon: "none" });
    }
  },

  // ============ 作品集（极简） ============

  async loadPortfolio() {
    if (!this.data.token) return;
    this.setData({ portfolioLoading: true });
    try {
      const app = getApp();
      const base = app.globalData.apiBaseUrl;
      const data = await this.studioRequest("/studio/portfolio");
      const items = (data.items || []).map((x) => ({
        ...x,
        display_url: x.watermark_url
          ? x.watermark_url.startsWith("/")
            ? base + x.watermark_url
            : x.watermark_url
          : x.image_url && x.image_url.startsWith("/")
          ? base + x.image_url
          : x.image_url
      }));
      this.setData({ items });
    } catch (e) {
      wx.showToast({ title: "加载作品失败", icon: "none" });
    } finally {
      this.setData({ portfolioLoading: false });
    }
  },

  async chooseAndUpload() {
    if (!this.data.token) {
      wx.showToast({ title: "请先登录", icon: "none" });
      return;
    }
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
      const app = getApp();
      const base = app.globalData.apiBaseUrl;
      // 自动复用用户的风格标签
      const autoTags = this.data.profileTagSelected.join(",");
      await Promise.all(
        files.map(async (file) => {
          const up = await uploadImageToS3Like({
            tempFilePath: file.tempFilePath,
            filename: file.tempFilePath.split("/").pop() || "image.jpg",
            contentType: file.fileType ? `image/${file.fileType}` : "image/jpeg",
            prefix: "portfolio"
          });
          const imageUrl = up.public_url || (up.proxy_url ? base + up.proxy_url : "");
          if (!imageUrl) throw new Error("no url");
          await this.studioRequest("/studio/portfolio", {
            method: "POST",
            data: {
              title: "",
              tags: autoTags,
              category: "",
              is_pinned: false,
              sort_order: 0,
              image_url: imageUrl,
              image_object_key: up.object_key || null
            }
          });
        })
      );
      this.setData({ lastUrl: "已上传 " + files.length + " 张" });
      wx.showToast({ title: "已上传", icon: "none" });
      await this.loadPortfolio();
    } catch (e) {
      wx.showToast({ title: "上传失败", icon: "none" });
    } finally {
      this.setData({ portfolioUploading: false, portfolioUploadCount: 0 });
    }
  },

  async togglePin(e) {
    const id = e.currentTarget.dataset.id;
    const item = this.data.items.find((x) => x.id === id);
    if (!item) return;
    try {
      await this.studioRequest(`/studio/portfolio/${id}`, {
        method: "PUT",
        data: { is_pinned: !item.is_pinned }
      });
      await this.loadPortfolio();
    } catch (e) {
      wx.showToast({ title: "操作失败", icon: "none" });
    }
  },

  async deleteItem(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: "确认删除",
      content: "删除后不可恢复，确定吗？",
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await this.studioRequest(`/studio/portfolio/${id}`, { method: "DELETE" });
          await this.loadPortfolio();
        } catch (e) {
          wx.showToast({ title: "删除失败", icon: "none" });
        }
      }
    });
  },

  // ============ 套餐管理 ============

  async loadPackages() {
    if (!this.data.token) return;
    this.setData({ packagesLoading: true });
    try {
      const data = await this.studioRequest("/studio/packages");
      const items = (data.items || []).map((x) => ({
        ...x,
        price_yuan: (x.price_cents / 100).toFixed(0),
        duration_minutes: x.duration_minutes || ""
      }));
      this.setData({ packages: items });
    } catch (e) {
      wx.showToast({ title: "加载套餐失败", icon: "none" });
    } finally {
      this.setData({ packagesLoading: false });
    }
  },

  // 一键使用预设套餐
  async applyPreset(e) {
    const index = e.currentTarget.dataset.index;
    const preset = this.data.presetPackages[index];
    if (!preset) return;
    try {
      const priceValue = parseFloat(preset.price_yuan || "0");
      await this.studioRequest("/studio/packages", {
        method: "POST",
        data: {
          name: preset.name,
          price_cents: Math.round((Number.isNaN(priceValue) ? 0 : priceValue) * 100),
          duration_minutes: preset.duration_minutes ? parseInt(preset.duration_minutes, 10) : null,
          description: preset.description || "",
          is_active: true
        }
      });
      wx.showToast({ title: "套餐已创建", icon: "none" });
      await this.loadPackages();
    } catch (e) {
      wx.showToast({ title: "创建失败", icon: "none" });
    }
  },

  showCustomPackage() {
    this.setData({ showNewPackage: true });
  },

  hideNewPackage() {
    this.setData({
      showNewPackage: false,
      newPackage: { name: "", price_yuan: "", duration_minutes: "", description: "", is_active: true }
    });
  },

  toggleNewPackage() {
    this.setData({ showNewPackage: !this.data.showNewPackage });
  },

  onPackageField(e) {
    const index = e.currentTarget.dataset.index;
    const field = e.currentTarget.dataset.field;
    const value = e.detail.value;
    const key = `packages[${index}].${field}`;
    this.setData({ [key]: value });
  },

  onNewPackageField(e) {
    const field = e.currentTarget.dataset.field;
    const value = e.detail.value;
    const key = `newPackage.${field}`;
    this.setData({ [key]: value });
  },

  async savePackage(e) {
    const index = e.currentTarget.dataset.index;
    const item = this.data.packages[index];
    if (!item) return;
    try {
      const priceValue = parseFloat(item.price_yuan || "0");
      await this.studioRequest(`/studio/packages/${item.id}`, {
        method: "PUT",
        data: {
          name: item.name,
          price_cents: Math.round((Number.isNaN(priceValue) ? 0 : priceValue) * 100),
          duration_minutes: item.duration_minutes ? parseInt(item.duration_minutes, 10) : null,
          description: item.description || "",
          is_active: !!item.is_active
        }
      });
      wx.showToast({ title: "已保存", icon: "none" });
    } catch (e) {
      wx.showToast({ title: "保存失败", icon: "none" });
    }
  },

  async addPackage() {
    const item = this.data.newPackage;
    if (!item.name) {
      wx.showToast({ title: "请填写套餐名称", icon: "none" });
      return;
    }
    try {
      const priceValue = parseFloat(item.price_yuan || "0");
      await this.studioRequest("/studio/packages", {
        method: "POST",
        data: {
          name: item.name,
          price_cents: Math.round((Number.isNaN(priceValue) ? 0 : priceValue) * 100),
          duration_minutes: item.duration_minutes ? parseInt(item.duration_minutes, 10) : null,
          description: item.description || "",
          is_active: !!item.is_active
        }
      });
      this.setData({
        showNewPackage: false,
        newPackage: { name: "", price_yuan: "", duration_minutes: "", description: "", is_active: true }
      });
      this.clearDraft();
      await this.loadPackages();
    } catch (e) {
      wx.showToast({ title: "创建失败", icon: "none" });
    }
  },

  async deletePackage(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: "确认删除",
      content: "删除后不可恢复，确定吗？",
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await this.studioRequest(`/studio/packages/${id}`, { method: "DELETE" });
          await this.loadPackages();
        } catch (e) {
          wx.showToast({ title: "删除失败", icon: "none" });
        }
      }
    });
  },

  // ============ 档期管理 ============

  toggleScheduleExpanded() {
    this.setData({ scheduleExpanded: !this.data.scheduleExpanded });
    if (this.data.scheduleExpanded && this.data.scheduleCells.length === 0) {
      this.loadSchedule();
    }
  },

  async loadSchedule() {
    if (!this.data.token) return;
    const year = this.data.scheduleYear;
    const month = this.data.scheduleMonth;
    const startDate = formatDate(year, month, 1);
    const endDate = formatDate(year, month, new Date(year, month, 0).getDate());
    this.setData({ scheduleLoading: true });
    try {
      const data = await this.studioRequest("/studio/schedule", {
        params: { start_date: startDate, end_date: endDate }
      });
      const map = {};
      (data.items || []).forEach((x) => {
        map[x.date] = x.status;
      });
      this.setData({
        scheduleMap: map,
        scheduleCells: buildCalendar(year, month, map)
      });
    } catch (e) {
      wx.showToast({ title: "加载档期失败", icon: "none" });
    } finally {
      this.setData({ scheduleLoading: false });
    }
  },

  async changeMonth(e) {
    const delta = parseInt(e.currentTarget.dataset.delta, 10);
    let y = this.data.scheduleYear;
    let m = this.data.scheduleMonth + delta;
    if (m <= 0) {
      y -= 1;
      m = 12;
    } else if (m > 12) {
      y += 1;
      m = 1;
    }
    this.setData({ scheduleYear: y, scheduleMonth: m });
    await this.loadSchedule();
  },

  async tapDay(e) {
    const date = e.currentTarget.dataset.date;
    if (!date) return;
    wx.showActionSheet({
      itemList: ["设为忙碌", "设为不可约", "清除"],
      success: async (res) => {
        try {
          if (res.tapIndex === 2) {
            await this.studioRequest(`/studio/schedule/${date}`, { method: "DELETE" });
          } else {
            const status = res.tapIndex === 0 ? "busy" : "blocked";
            await this.studioRequest("/studio/schedule", { method: "PUT", data: { date, status } });
          }
          await this.loadSchedule();
        } catch (e) {
          wx.showToast({ title: "更新档期失败", icon: "none" });
        }
      }
    });
  }
});
