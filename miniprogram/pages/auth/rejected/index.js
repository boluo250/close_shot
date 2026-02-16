Page({
  data: {
    reason: "",
  },

  onLoad(query) {
    const reason = query?.reason ? decodeURIComponent(query.reason) : "";
    this.setData({ reason });
  },

  reApply() {
    wx.redirectTo({ url: "/pages/auth/apply/index" });
  },

  onBackMine() {
    wx.reLaunch({ url: "/pages/home/index?tab=mine" });
  },
});
