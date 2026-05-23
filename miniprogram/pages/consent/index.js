const { hasAcceptedConsent, markConsentAccepted } = require("../../utils/consent");

Page({
  data: {
    agreed: false,
    submitting: false
  },

  onLoad() {
    this.redirectIfAccepted();
  },

  onShow() {
    this.redirectIfAccepted();
  },

  toggleAgree() {
    this.setData({ agreed: !this.data.agreed });
  },

  goAgreement() {
    wx.navigateTo({ url: "/pages/agreement/index" });
  },

  goPrivacy() {
    wx.navigateTo({ url: "/pages/privacy/index" });
  },

  acceptAndEnter() {
    if (!this.data.agreed) {
      wx.showToast({ title: "请先勾选同意协议", icon: "none" });
      return;
    }
    if (this.data.submitting) return;

    this.setData({ submitting: true });
    markConsentAccepted();
    wx.reLaunch({ url: "/pages/home/index" });
  },

  redirectIfAccepted() {
    if (!hasAcceptedConsent()) return;
    if (this._redirecting) return;

    this._redirecting = true;
    wx.reLaunch({ url: "/pages/home/index" });
  }
});
