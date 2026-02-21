const { getToken, setToken, ensureLogin } = require("../../utils/auth");
const { request } = require("../../utils/request");

Component({
  data: {
    token: "",
    loading: false,
    identityLoading: false,
    role: "",
    photographerStatus: "",
    rejectReason: "",
    stats: {
      favoriteCount: 0
    },
    profile: {
      nickname: "",
      avatarUrl: ""
    },
    uiText: {
      guestNickname: "游客",
      loginNickname: "微信用户",
      loginTitle: "微信一键登录",
      loggingInTitle: "登录中...",
      loginTip: "登录后可同步收藏，并继续摄影师认证流程。",
      logoutTitle: "退出登录",
      favoriteLabel: "收藏",
      studioTitle: "摄影师工作台",
      studioDescGuest: "登录后可申请成为摄影师",
      studioDescApproved: "进入工作台管理作品和资料",
      studioDescDefault: "提交或查看认证进度",
      sectionTitle: "常用功能",
      editProfileTitle: "编辑摄影师主页",
      editProfileDesc: "更新主页信息、接单状态与作品展示",
      certTitle: "认证中心",
      certDesc: "查看认证进度和审核结果",
      statusGuest: "未登录",
      statusUser: "普通用户",
      statusAdmin: "管理员",
      certApproved: "已认证",
      certPending: "审核中",
      certRejected: "未通过",
      certNotApplied: "未认证",
      certLoading: "状态查询中"
    },
    viewState: {
      avatarText: "游",
      nickname: "游客",
      roleLabel: "未登录",
      certLabel: "未认证",
      studioDesc: "登录后可申请成为摄影师"
    }
  },
  lifetimes: {
    attached() {
      this.refresh();
    }
  },
  methods: {
    refresh() {
      this.setData({ token: getToken() || "" });
      this.syncViewState();
      this.loadIdentity();
      this.loadFavoriteCount();
    },

    syncViewState() {
      const { token, role, photographerStatus, identityLoading, profile, uiText } = this.data;
      let roleLabel = uiText.statusGuest;
      if (token) {
        roleLabel = role === "admin" ? uiText.statusAdmin : uiText.statusUser;
      }

      let certLabel = uiText.certNotApplied;
      if (identityLoading && token) certLabel = uiText.certLoading;
      else if (photographerStatus === "approved") certLabel = uiText.certApproved;
      else if (photographerStatus === "pending") certLabel = uiText.certPending;
      else if (photographerStatus === "rejected") certLabel = uiText.certRejected;

      let studioDesc = uiText.studioDescGuest;
      if (token) {
        studioDesc = photographerStatus === "approved" ? uiText.studioDescApproved : uiText.studioDescDefault;
      }

      this.setData({
        viewState: {
          avatarText: token ? "我" : "游",
          nickname: profile.nickname || (token ? uiText.loginNickname : uiText.guestNickname),
          roleLabel,
          certLabel,
          studioDesc
        }
      });
    },

    async loadFavoriteCount() {
      const token = getToken();
      if (!token) {
        this.setData({ "stats.favoriteCount": 0 });
        return;
      }
      try {
        const list = await request("/me/favorites", { auth: true });
        this.setData({ "stats.favoriteCount": Array.isArray(list) ? list.length : 0 });
      } catch (e) {
        this.setData({ "stats.favoriteCount": 0 });
      }
    },

    async loadIdentity() {
      const token = getToken();
      if (!token) {
        this.setData({ role: "", photographerStatus: "not_applied", rejectReason: "", identityLoading: false });
        this.syncViewState();
        return;
      }
      this.setData({ identityLoading: true });
      this.syncViewState();
      try {
        const data = await request("/me/identity", { auth: true });
        this.setData({
          role: data.role || "",
          photographerStatus: data.photographer_status || "not_applied",
          rejectReason: data.photographer_reject_reason || ""
        });
      } catch (e) {
        this.setData({ role: "", photographerStatus: "not_applied", rejectReason: "" });
      } finally {
        this.setData({ identityLoading: false });
        this.syncViewState();
      }
    },

    async login() {
      this.setData({ loading: true });
      try {
        const t = await ensureLogin();
        this.setData({ token: t || "" });
        await Promise.all([this.loadIdentity(), this.loadFavoriteCount()]);
        this.syncViewState();
        wx.showToast({ title: "已登录", icon: "none" });
      } catch (e) {
        wx.showToast({ title: e?.message || "登录失败", icon: "none" });
      } finally {
        this.setData({ loading: false });
      }
    },

    logout() {
      setToken("");
      this.setData({
        token: "",
        role: "",
        photographerStatus: "not_applied",
        rejectReason: "",
        "stats.favoriteCount": 0
      });
      this.syncViewState();
      wx.showToast({ title: "已退出", icon: "none" });
    },

    goFavorites() {
      // 由父容器决定是“同页切换”还是“跳转页面”
      this.triggerEvent("gofavorites");
    },

    goEditPhotographerProfile() {
      if (!this.data.token) {
        wx.showToast({ title: "请先登录", icon: "none" });
        return;
      }
      if (this.data.photographerStatus !== "approved") {
        wx.showToast({ title: "认证通过后可编辑", icon: "none" });
        return;
      }
      wx.navigateTo({ url: "/pages/studio/index" });
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

