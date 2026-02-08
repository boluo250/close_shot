const { request } = require("../../../utils/request");

Page({
  data: {
    submitting: false
  },

  async submitApply() {
    if (this.data.submitting) return;
    this.setData({ submitting: true });
    try {
      await request("/me/photographer/apply", { method: "POST", auth: true });
      wx.showToast({ title: "已提交，等待审核", icon: "none" });
      wx.navigateTo({ url: "/pages/auth/review/index" });
    } catch (e) {
      wx.showToast({ title: "提交失败，请稍后重试", icon: "none" });
    } finally {
      this.setData({ submitting: false });
    }
  }
});
