const { request } = require("../../utils/request");
const { ensureLogin } = require("../../utils/auth");
const { uploadImageToS3Like } = require("../../utils/upload");
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

Page({
  data: {
    token: "",
    authorized: false,
    checkingIdentity: false,
    loading: false,
    profileLoading: false,
    profileSaving: false,
    portfolioLoading: false,
    portfolioUploading: false,
    portfolioUploadCount: 0,
    packagesLoading: false,
    scheduleLoading: false,
    lastUrl: "",
    profile: {
      bio: "",
      tags: "",
      avatar_url: "",
      cover_url: ""
    },
    avatarObjectKey: "",
    coverObjectKey: "",
    profileTagOptions: ["日系", "复古", "法式", "胶片", "纪实", "清新", "高级感"],
    profileTagSelected: [],
    portfolioForm: {
      title: "",
      tags: "",
      category: "",
      is_pinned: false
    },
    items: [],
    packages: [],
    newPackage: {
      name: "",
      price_yuan: "",
      duration_minutes: "",
      description: "",
      is_active: true
    },
    scheduleYear: new Date().getFullYear(),
    scheduleMonth: new Date().getMonth() + 1,
    scheduleCells: [],
    scheduleMap: {}
  },

  onLoad() {
    this.checkAndEnter();
  },

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

  onTitle(e) {
    this.setData({ "portfolioForm.title": e.detail.value });
  },
  onTags(e) {
    this.setData({ "portfolioForm.tags": e.detail.value });
  },
  onCategory(e) {
    this.setData({ "portfolioForm.category": e.detail.value });
  },
  onPinSwitch(e) {
    this.setData({ "portfolioForm.is_pinned": e.detail.value });
  },
  onBio(e) {
    this.setData({ "profile.bio": e.detail.value });
  },

  logout() {
    this.setData({ token: "", authorized: false, items: [], packages: [] });
  },

  async refreshAll() {
    if (!this.data.token) return;
    await Promise.all([this.loadProfile(), this.loadPortfolio(), this.loadPackages(), this.loadSchedule()]);
  },

  async loadProfile() {
    if (!this.data.token) return;
    this.setData({ profileLoading: true });
    try {
      const data = await this.studioRequest("/studio/me");
      const profile = data.photographer || {};
      const selected = (profile.tags || "")
        .split(",")
        .map((t) => t.trim())
        .filter((t) => t);
      this.setData({
        profile: {
          bio: profile.bio || "",
          tags: profile.tags || "",
          avatar_url: profile.avatar_url || "",
          cover_url: profile.cover_url || ""
        },
        profileTagSelected: selected
      });
    } catch (e) {
      wx.showToast({ title: "加载资料失败", icon: "none" });
    } finally {
      this.setData({ profileLoading: false });
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
        cover_object_key: this.data.coverObjectKey || null
      };
      await this.studioRequest("/studio/me", { method: "PUT", data: payload });
      this.setData({ "profile.tags": tags, avatarObjectKey: "", coverObjectKey: "" });
      wx.showToast({ title: "资料已保存", icon: "none" });
    } catch (e) {
      wx.showToast({ title: "资料保存失败", icon: "none" });
    } finally {
      this.setData({ profileSaving: false });
    }
  },

  toggleProfileTag(e) {
    const tag = e.currentTarget.dataset.tag;
    const selected = new Set(this.data.profileTagSelected);
    if (selected.has(tag)) selected.delete(tag);
    else selected.add(tag);
    this.setData({ profileTagSelected: Array.from(selected) });
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
              title: this.data.portfolioForm.title,
              tags: this.data.portfolioForm.tags,
              category: this.data.portfolioForm.category,
              is_pinned: this.data.portfolioForm.is_pinned,
              sort_order: 0,
              image_url: imageUrl,
              image_object_key: up.object_key || null
            }
          });
        })
      );
      this.setData({
        lastUrl: "已上传 " + files.length + " 张",
        "portfolioForm.title": "",
        "portfolioForm.tags": "",
        "portfolioForm.category": "",
        "portfolioForm.is_pinned": false
      });
      wx.showToast({ title: "已创建作品", icon: "none" });
      await this.loadPortfolio();
    } catch (e) {
      wx.showToast({ title: "上传/创建失败", icon: "none" });
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

  onItemCategory(e) {
    const index = e.currentTarget.dataset.index;
    const value = e.detail.value;
    const key = `items[${index}].category`;
    this.setData({ [key]: value });
  },

  async saveItemCategory(e) {
    const index = e.currentTarget.dataset.index;
    const item = this.data.items[index];
    if (!item) return;
    try {
      await this.studioRequest(`/studio/portfolio/${item.id}`, {
        method: "PUT",
        data: { category: item.category || "" }
      });
      wx.showToast({ title: "已保存分类", icon: "none" });
    } catch (e) {
      wx.showToast({ title: "保存失败", icon: "none" });
    }
  },

  async deleteItem(e) {
    const id = e.currentTarget.dataset.id;
    try {
      await this.studioRequest(`/studio/portfolio/${id}`, { method: "DELETE" });
      await this.loadPortfolio();
    } catch (e) {
      wx.showToast({ title: "删除失败", icon: "none" });
    }
  },

  async loadPackages() {
    if (!this.data.token) return;
    this.setData({ packagesLoading: true });
    try {
      const data = await this.studioRequest("/studio/packages");
      const items = (data.items || []).map((x) => ({
        ...x,
        price_yuan: (x.price_cents / 100).toFixed(2),
        duration_minutes: x.duration_minutes || ""
      }));
      this.setData({ packages: items });
    } catch (e) {
      wx.showToast({ title: "加载套餐失败", icon: "none" });
    } finally {
      this.setData({ packagesLoading: false });
    }
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
      wx.showToast({ title: "已保存套餐", icon: "none" });
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
        newPackage: { name: "", price_yuan: "", duration_minutes: "", description: "", is_active: true }
      });
      await this.loadPackages();
    } catch (e) {
      wx.showToast({ title: "创建失败", icon: "none" });
    }
  },

  async deletePackage(e) {
    const id = e.currentTarget.dataset.id;
    try {
      await this.studioRequest(`/studio/packages/${id}`, { method: "DELETE" });
      await this.loadPackages();
    } catch (e) {
      wx.showToast({ title: "删除失败", icon: "none" });
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

