const { getToken, clearAuthState, ensureLogin } = require("../../utils/auth");
const { request } = require("../../utils/request");
const env = require("../../env");

Page({
  data: {
    enableDevTools: !!env.ENABLE_DEV_TOOLS,
    token: "",
    loading: false,
    identityLoading: false,
    role: "",
    photographerStatus: "",
    rejectReason: "",
    profile: {
      nickname: "",
      avatarUrl: ""
    },
    membership: {
      isMember: false,
      expiresAt: "",
      loading: false
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
      membershipTitle: "开通会员",
      membershipDescGuest: "登录后立即开通，解锁联系方式查看",
      membershipDescNonMember: "开通后可查看摄影师联系方式",
      membershipDescMember: "会员已开通，可持续查看联系方式",
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

  onShow() {
    this.refresh();
  },

  refresh() {
    this.setData({ token: getToken() || "" });
    this.syncViewState();
    this.loadIdentity();
    this.loadMembership();
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

  _formatMemberExpireText(expiresAt) {
    if (!expiresAt) return "";
    const dt = new Date(expiresAt);
    if (Number.isNaN(dt.getTime())) return "";
    const y = dt.getFullYear();
    const m = String(dt.getMonth() + 1).padStart(2, "0");
    const d = String(dt.getDate()).padStart(2, "0");
    return `${y}.${m}.${d} 到期`;
  },

  async loadMembership() {
    const token = getToken();
    if (!token) {
      this.setData({ membership: { isMember: false, expiresAt: "", loading: false } });
      return;
    }
    this.setData({ "membership.loading": true });
    try {
      const data = await request("/membership/me", { auth: true });
      this.setData({
        membership: {
          isMember: !!data?.is_member,
          expiresAt: this._formatMemberExpireText(data?.member_expires_at),
          loading: false
        }
      });
    } catch (_e) {
      this.setData({ membership: { isMember: false, expiresAt: "", loading: false } });
    }
  },

  async login() {
    this.setData({ loading: true });
    try {
      const t = await ensureLogin();
      this.setData({ token: t || "" });
      await Promise.all([this.loadIdentity(), this.loadMembership()]);
      this.syncViewState();
      wx.showToast({ title: "已登录", icon: "none" });
    } catch (e) {
      wx.showToast({ title: e?.message || "登录失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },

  logout() {
    clearAuthState();
    this.setData({
      token: "",
      role: "",
      photographerStatus: "not_applied",
      rejectReason: "",
      membership: { isMember: false, expiresAt: "", loading: false }
    });
    this.syncViewState();
    wx.showToast({ title: "已退出", icon: "none" });
  },

  clearLocalAuthCache() {
    clearAuthState();
    this.setData({
      token: "",
      role: "",
      photographerStatus: "not_applied",
      rejectReason: "",
      membership: { isMember: false, expiresAt: "", loading: false }
    });
    this.syncViewState();
    wx.showToast({ title: "本地认证缓存已清理", icon: "none" });
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
  },

  async goMembership() {
    wx.showLoading({ title: "加载中..." });
    try {
      await ensureLogin();
      const plans = await request("/membership/plans");
      if (!Array.isArray(plans) || !plans.length) {
        wx.showToast({ title: "暂无可购买套餐", icon: "none" });
        return;
      }
      wx.hideLoading();
      const itemList = plans.map((x) => `${x.title} ¥${((x.price_cents || 0) / 100).toFixed(0)}`);
      const selected = await new Promise((resolve, reject) => {
        wx.showActionSheet({
          itemList,
          success: (res) => resolve(res.tapIndex),
          fail: reject
        });
      });
      const idx = Number(selected);
      const target = plans[idx];
      if (!target) return;
      await request("/membership/orders", {
        method: "POST",
        data: { plan_code: target.code },
        auth: true
      });
      wx.showModal({
        title: "订单已创建",
        content: "支付能力接入中，订单已生成。接入支付后会自动完成会员开通。",
        showCancel: false
      });
      await this.loadMembership();
    } catch (_e) {
      wx.showToast({ title: "暂未完成购买", icon: "none" });
    } finally {
      wx.hideLoading();
    }
  }
});

