const { request } = require("../../../utils/request");
const { ensureLogin } = require("../../../utils/auth");

Page({
  data: {
    status: "pending",
    certLevel: 0,
    identityVerified: false,
    portfolioUploaded: false,
    contactVerified: false,
  },

  onLoad() {
    this._loadStatus();
  },

  onShow() {
    this._loadStatus();
  },

  async _loadStatus() {
    try {
      await ensureLogin();
      const res = await request("/me/photographer/certification", { method: "GET", auth: true });

      if (res.status === "approved") {
        wx.showToast({ title: "认证已通过！", icon: "success" });
        setTimeout(() => {
          wx.reLaunch({ url: "/pages/home/index?tab=mine" });
        }, 1500);
        return;
      }

      if (res.status === "rejected") {
        wx.redirectTo({
          url: "/pages/auth/rejected/index?reason=" + encodeURIComponent(res.reject_reason || ""),
        });
        return;
      }

      this.setData({
        status: res.status,
        certLevel: res.certification_level,
        identityVerified: res.identity_verified,
        portfolioUploaded: res.portfolio_uploaded,
        contactVerified: res.contact_verified,
      });
    } catch (e) {
      // ignore
    }
  },

  onBackMine() {
    wx.reLaunch({ url: "/pages/home/index?tab=mine" });
  },

  onRefresh() {
    this._loadStatus();
    wx.showToast({ title: "已刷新", icon: "none" });
  },
});
