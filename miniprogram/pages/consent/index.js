const CONSENT_STORAGE_KEY = "cs_legal_consent_v1";

Page({
  data: {
    agreed: false,
    submitting: false
  },

  onLoad() {
    const accepted = !!wx.getStorageSync(CONSENT_STORAGE_KEY);
    if (accepted) {
      wx.reLaunch({ url: "/pages/home/index" });
    }
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
    wx.setStorageSync(CONSENT_STORAGE_KEY, {
      agreed: true,
      acceptedAt: Date.now()
    });
    wx.reLaunch({ url: "/pages/home/index" });
  }
});
