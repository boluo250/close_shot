const { request } = require("../../../utils/request");
const { ensureLogin } = require("../../../utils/auth");

Page({
  data: {
    reason: "",
    submitting: false
  },

  onLoad(query) {
    const reason = query?.reason ? decodeURIComponent(query.reason) : "";
    this.setData({ reason });
  },

  async resubmit() {
    if (this.data.submitting) return;
    this.setData({ submitting: true });
    try {
      await ensureLogin();
      await request("/me/photographer/apply", { method: "POST", auth: true });
      wx.showToast({ title: "已重新提交", icon: "none" });
      wx.navigateTo({ url: "/pages/auth/review/index" });
    } catch (e) {
      wx.showToast({ title: "提交失败，请稍后重试", icon: "none" });
    } finally {
      this.setData({ submitting: false });
    }
  },

  onBackMine() {
    wx.switchTab({ url: "/pages/mine/index" });
  }
});
