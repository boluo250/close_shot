const { ensureLogin, getToken } = require("../../../utils/auth");
const { request } = require("../../../utils/request");
const {
  warmAppointmentSubscribeConfig,
  requestCustomerAppointmentAcceptedSubscription
} = require("../../../utils/subscribe");

function buildDefaultDate() {
  const now = new Date();
  now.setDate(now.getDate() + 1);
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
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
      shootingType: "",
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
    this.setData({ photographerId });
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

  async submit() {
    const { date, time, locationText, contactName, contactPhone, shootingType, participantCount, note } = this.data.form;
    if (!locationText.trim()) {
      wx.showToast({ title: "请填写拍摄地点", icon: "none" });
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
          contact_name: contactName.trim(),
          contact_phone: contactPhone.trim(),
          shooting_type: shootingType.trim(),
          participant_count: Number(participantCount || 1),
          note: note.trim()
        }
      });
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
