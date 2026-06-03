const { ensureLogin, getToken } = require("../../../utils/auth");
const { request } = require("../../../utils/request");
const {
  warmAppointmentSubscribeConfig,
  requestCustomerAppointmentAcceptedSubscription
} = require("../../../utils/subscribe");

const CUSTOMER_CONTACT_CACHE_KEY = "appointment_customer_contact_cache_v1";

function buildDefaultDate() {
  const now = new Date();
  now.setDate(now.getDate() + 1);
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function normalizeLocationText(choice) {
  const name = (choice?.name || "").trim();
  const address = (choice?.address || "").trim();
  if (name && address && address.includes(name)) {
    return address.slice(0, 255);
  }
  if (name && address) {
    return `${name} ${address}`.slice(0, 255);
  }
  return (name || address || "").slice(0, 255);
}

function getSettingAsync() {
  if (typeof wx.getSetting !== "function") {
    return Promise.resolve({});
  }
  return new Promise((resolve, reject) => {
    wx.getSetting({
      success: resolve,
      fail: reject
    });
  });
}

function authorizeAsync(scope) {
  if (typeof wx.authorize !== "function") {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    wx.authorize({
      scope,
      success: resolve,
      fail: reject
    });
  });
}

function showModalAsync(options) {
  return new Promise((resolve) => {
    wx.showModal({
      ...options,
      success: resolve,
      fail: () => resolve({ confirm: false, cancel: true })
    });
  });
}

function openSettingAsync() {
  if (typeof wx.openSetting !== "function") {
    return Promise.resolve({});
  }
  return new Promise((resolve, reject) => {
    wx.openSetting({
      success: resolve,
      fail: reject
    });
  });
}

function loadCachedCustomerContact() {
  try {
    const cached = wx.getStorageSync(CUSTOMER_CONTACT_CACHE_KEY) || {};
    return {
      contactName: (cached.contactName || "").slice(0, 64),
      contactPhone: (cached.contactPhone || "").slice(0, 20)
    };
  } catch (_e) {
    return {
      contactName: "",
      contactPhone: ""
    };
  }
}

function saveCustomerContactCache(contactName, contactPhone) {
  try {
    wx.setStorageSync(CUSTOMER_CONTACT_CACHE_KEY, {
      contactName: (contactName || "").slice(0, 64),
      contactPhone: (contactPhone || "").slice(0, 20)
    });
  } catch (_e) {
    // Storage failure should not block appointment submission.
  }
}

Page({
  data: {
    photographerId: null,
    photographerName: "",
    packageOptions: [{ id: null, label: "不指定套餐" }],
    packageIndex: 0,
    submitting: false,
    form: {
      date: buildDefaultDate(),
      time: "10:00",
      locationText: "",
      contactName: "",
      contactPhone: "",
      participantCount: "1",
      note: ""
    }
  },

  async onLoad(query) {
    const photographerId = Number(query.photographerId || 0);
    if (!photographerId) {
      wx.showToast({ title: "缺少摄影师信息", icon: "none" });
      return;
    }
    const cachedContact = loadCachedCustomerContact();
    this.setData({
      photographerId,
      "form.contactName": cachedContact.contactName,
      "form.contactPhone": cachedContact.contactPhone
    });
    this.prepareAppointmentSubscriptions();
    await this.loadPhotographer();
  },

  prepareAppointmentSubscriptions() {
    if (!getToken()) return;
    warmAppointmentSubscribeConfig();
  },

  async loadPhotographer() {
    try {
      const data = await request(`/photographers/${this.data.photographerId}`, { auth: !!getToken() });
      const packageOptions = [{ id: null, label: "不指定套餐" }].concat(
        (data.packages || [])
          .filter((item) => item.is_active)
          .map((item) => ({
            id: item.id,
            label: `${item.name} · ¥${((item.price_cents || 0) / 100).toFixed(0)}`
          }))
      );
      this.setData({
        photographerName: data.display_name || `摄影师 #${this.data.photographerId}`,
        packageOptions
      });
    } catch (e) {
      wx.showToast({ title: e?.message || "加载失败", icon: "none" });
    }
  },

  bindInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`form.${field}`]: e.detail.value });
  },

  bindDateChange(e) {
    this.setData({ "form.date": e.detail.value });
  },

  bindTimeChange(e) {
    this.setData({ "form.time": e.detail.value });
  },

  bindPackageChange(e) {
    this.setData({ packageIndex: Number(e.detail.value || 0) });
  },

  async ensureLocationPermission() {
    try {
      const setting = await getSettingAsync();
      const authSetting = setting?.authSetting || {};
      const scopeState = authSetting["scope.userLocation"];
      if (scopeState === true) {
        return true;
      }
      if (scopeState === false) {
        const modal = await showModalAsync({
          title: "需要定位权限",
          content: "地图选点需要使用定位权限，请先在设置中打开后再继续。",
          confirmText: "去设置",
          cancelText: "手动填写"
        });
        if (!modal.confirm) return false;
        const result = await openSettingAsync();
        return !!result?.authSetting?.["scope.userLocation"];
      }
      await authorizeAsync("scope.userLocation");
      return true;
    } catch (err) {
      console.warn("ensureLocationPermission failed", err);
      const message = err?.errMsg || "";
      if (message.includes("auth deny") || message.includes("auth denied")) {
        wx.showToast({ title: "未开启定位权限，请手动填写", icon: "none" });
        return false;
      }
      wx.showToast({ title: "定位权限获取失败", icon: "none" });
      return false;
    }
  },

  async pickLocation() {
    if (typeof wx.chooseLocation !== "function") {
      wx.showToast({ title: "当前微信版本暂不支持地图选点", icon: "none" });
      return;
    }
    const hasPermission = await this.ensureLocationPermission();
    if (!hasPermission) return;
    wx.chooseLocation({
      success: (res) => {
        const locationText = normalizeLocationText(res);
        if (!locationText) return;
        this.setData({ "form.locationText": locationText });
      },
      fail: (err) => {
        console.warn("chooseLocation failed", err);
        const message = err?.errMsg || "";
        if (message.includes("cancel")) return;
        if (message.includes("auth deny") || message.includes("auth denied")) {
          wx.showToast({ title: "请允许地图定位后再选点", icon: "none" });
          return;
        }
        if (message.includes("system permission denied") || message.includes("system permission is denied")) {
          wx.showToast({ title: "请打开系统定位后重试", icon: "none" });
          return;
        }
        wx.showToast({ title: "地图选点失败，请手动填写", icon: "none" });
      }
    });
  },

  async submit() {
    const { date, time, locationText, contactName, contactPhone, participantCount, note } = this.data.form;
    const normalizedContactName = (contactName || "").trim();
    const normalizedContactPhone = (contactPhone || "").trim();
    if (!locationText.trim()) {
      wx.showToast({ title: "请填写拍摄地点", icon: "none" });
      return;
    }
    if (normalizedContactPhone && normalizedContactPhone.length < 5) {
      wx.showToast({ title: "请填写有效联系方式", icon: "none" });
      return;
    }
    this.setData({ submitting: true });
    try {
      await ensureLogin();
      this.prepareAppointmentSubscriptions();
      await requestCustomerAppointmentAcceptedSubscription();
      const packageOption = this.data.packageOptions[this.data.packageIndex] || { id: null };
      await request("/appointments", {
        method: "POST",
        auth: true,
        data: {
          photographer_id: this.data.photographerId,
          package_id: packageOption.id,
          scheduled_at: `${date}T${time}:00+08:00`,
          location_text: locationText.trim(),
          contact_name: normalizedContactName,
          contact_phone: normalizedContactPhone,
          participant_count: Number(participantCount || 1),
          note: note.trim()
        }
      });
      saveCustomerContactCache(normalizedContactName, normalizedContactPhone);
      wx.showModal({
        title: "预约已提交",
        content: "你可以在“我的 -> 预约中心”里查看这条预约记录。",
        confirmText: "去查看",
        cancelText: "返回我的",
        success: (res) => {
          if (res.confirm) {
            wx.redirectTo({ url: "/pages/appointments/index?tab=mine" });
            return;
          }
          wx.redirectTo({ url: "/pages/mine/index" });
        }
      });
    } catch (e) {
      wx.showToast({ title: e?.message || "提交失败", icon: "none" });
    } finally {
      this.setData({ submitting: false });
    }
  }
});
