const { getToken, setToken, ensureLogin } = require("../../utils/auth");
const { request } = require("../../utils/request");

Component({
  data: {
    token: "",
    loading: false,
    identityLoading: false,
    photographerStatus: "",
    rejectReason: ""
  },
  lifetimes: {
    attached() {
      this.refresh();
    }
  },
  methods: {
    refresh() {
      this.setData({ token: getToken() || "" });
      this.loadIdentity();
    },

    async loadIdentity() {
      const token = getToken();
      if (!token) {
        this.setData({ photographerStatus: "not_applied", rejectReason: "", identityLoading: false });
        return;
      }
      this.setData({ identityLoading: true });
      try {
        const data = await request("/me/identity", { auth: true });
        this.setData({
          photographerStatus: data.photographer_status || "not_applied",
          rejectReason: data.photographer_reject_reason || ""
        });
      } catch (e) {
        this.setData({ photographerStatus: "not_applied", rejectReason: "" });
      } finally {
        this.setData({ identityLoading: false });
      }
    },

    async login() {
      this.setData({ loading: true });
      try {
        const t = await ensureLogin();
        this.setData({ token: t || "" });
        wx.showToast({ title: "已登录", icon: "none" });
      } catch (e) {
        wx.showToast({ title: "登录失败", icon: "none" });
      } finally {
        this.setData({ loading: false });
      }
    },

    logout() {
      setToken("");
      this.setData({ token: "" });
      wx.showToast({ title: "已退出", icon: "none" });
    },

    goFavorites() {
      // 由父容器决定是“同页切换”还是“跳转页面”
      this.triggerEvent("gofavorites");
    },

    async goStudio() {
      wx.showLoading({ title: "加载中..." });
      try {
        await ensureLogin();
        const data = await request("/me/identity", { auth: true });
        const status = data.photographer_status;
        const isApproved = data.role === "admin" || status === "approved";
        if (isApproved) {
          wx.navigateTo({ url: "/pages/studio/index" });
        } else if (status === "pending") {
          wx.navigateTo({ url: "/pages/auth/review/index" });
        } else if (status === "rejected") {
          const reason = data.photographer_reject_reason || "";
          wx.navigateTo({
            url: `/pages/auth/rejected/index?reason=${encodeURIComponent(reason)}`
          });
        } else {
          wx.navigateTo({ url: "/pages/auth/apply/index" });
        }
      } catch (e) {
        wx.showToast({ title: "身份校验失败", icon: "none" });
      } finally {
        wx.hideLoading();
      }
    }
  }
});

