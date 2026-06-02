const { getToken, clearAuthState, ensureLogin } = require("../../utils/auth");
const { request } = require("../../utils/request");
const {
  warmAppointmentSubscribeConfig,
  requestPhotographerAppointmentSubscriptions,
  summarizeAppointmentSubscribeResult,
  clearAppointmentSubscribeCache
} = require("../../utils/subscribe");
const IDENTITY_CACHE_KEY = "mine_identity_cache_v1";
const APPOINTMENT_PROMPT_CACHE_KEY = "mine_appointment_prompt_cache_v1";
const PHOTOGRAPHER_NOTIFY_PROMPT_KEY = "photographer_notify_prompt_v1";

Page({
  data: {
    token: "",
    loading: false,
    identityLoading: false,
    notificationActionLoading: false,
    identityState: "unknown",
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
    appointmentSummary: {
      mineWaitingCustomerConfirm: 0,
      mineWaitingCompletionConfirm: 0,
      mineCompletedWithoutReview: 0,
      assignedPendingDecision: 0,
      assignedWaitingCustomerConfirm: 0,
      assignedWaitingCompletionMark: 0,
      minePendingTotal: 0,
      assignedPendingTotal: 0,
      centerPendingTotal: 0
    },
    uiText: {
      guestNickname: "游客",
      loginNickname: "微信用户",
      loginTitle: "微信一键登录",
      loggingInTitle: "登录中...",
      loginTip: "登录后可同步收藏，并继续摄影师入驻流程。",
      logoutTitle: "退出登录",
      favoriteLabel: "收藏",
      studioTitle: "摄影师工作台",
      studioDescGuest: "登录后可申请成为摄影师",
      studioDescApproved: "进入工作台管理作品和资料",
      studioDescDefault: "提交入驻资料或查看审核状态",
      sectionTitle: "常用功能",
      editProfileTitle: "编辑摄影师主页",
      editProfileDesc: "更新主页信息、接单状态与作品展示",
      certTitle: "入驻中心",
      certDesc: "提交入驻资料和查看审核状态",
      membershipTitle: "开通会员",
      membershipDescGuest: "登录后立即开通，解锁联系方式查看",
      membershipDescNonMember: "开通后可查看摄影师联系方式",
      membershipDescMember: "会员已开通，可持续查看联系方式",
      statusGuest: "未登录",
      statusUser: "普通用户",
      statusAdmin: "管理员",
      certApproved: "已入驻",
      certPending: "审核中",
      certRejected: "需修改",
      certNotApplied: "未提交",
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
    const token = getToken() || "";
    const cached = token ? this._readIdentityCache(token) : null;
    if (!token) {
      this.setData({
        token: "",
        identityLoading: false,
        identityState: "guest",
        role: "",
        photographerStatus: "not_applied",
        rejectReason: ""
      });
    } else if (cached) {
      this.setData({
        token,
        identityLoading: false,
        identityState: this._deriveIdentityState(token, cached.role, cached.photographerStatus),
        role: cached.role || "",
        photographerStatus: cached.photographerStatus || "not_applied",
        rejectReason: cached.rejectReason || ""
      });
    } else {
      this.setData({
        token,
        identityLoading: true,
        identityState: "unknown",
        role: "",
        photographerStatus: "not_applied",
        rejectReason: ""
      });
    }
    this.syncViewState();
    if (token) warmAppointmentSubscribeConfig();
    this.loadIdentity();
    this.loadMembership();
    this.loadAppointmentSummary();
  },

  syncViewState() {
    const { token, role, photographerStatus, identityState, profile, uiText } = this.data;
    let roleLabel = uiText.statusGuest;
    if (token) {
      roleLabel = role === "admin" ? uiText.statusAdmin : uiText.statusUser;
    }

    let certLabel = uiText.certNotApplied;
    if (identityState === "unknown" && token) certLabel = uiText.certLoading;
    else if (identityState === "verified_photographer") certLabel = uiText.certApproved;
    else if (photographerStatus === "pending") certLabel = uiText.certPending;
    else if (photographerStatus === "rejected") certLabel = uiText.certRejected;

    let studioDesc = uiText.studioDescGuest;
    if (identityState === "unknown") studioDesc = uiText.certLoading;
    else if (token) {
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
      this.setData({
        role: "",
        photographerStatus: "not_applied",
        rejectReason: "",
        identityLoading: false,
        identityState: "guest"
      });
      this.syncViewState();
      return;
    }
    if (this.data.identityState === "unknown") {
      this.setData({ identityLoading: true });
    }
    this.syncViewState();
    try {
      const data = await request("/me/identity", { auth: true });
      const role = data.role || "";
      const photographerStatus = data.photographer_status || "not_applied";
      const rejectReason = data.photographer_reject_reason || "";
      const previousIdentityState = this.data.identityState;
      const previousPhotographerStatus = this.data.photographerStatus;
      this.setData({
        role,
        photographerStatus,
        rejectReason,
        identityState: this._deriveIdentityState(token, role, photographerStatus)
      });
      this._writeIdentityCache(token, { role, photographerStatus, rejectReason });
      this.maybePromptPhotographerNotifications({
        token,
        role,
        photographerStatus,
        previousIdentityState,
        previousPhotographerStatus
      });
    } catch (e) {
      if (this.data.identityState === "unknown") {
        this.setData({
          role: "",
          photographerStatus: "not_applied",
          rejectReason: "",
          identityState: "logged_in_unverified"
        });
      }
    } finally {
      this.setData({ identityLoading: false });
      this.syncViewState();
      this.maybeShowAppointmentPrompt();
    }
  },

  _deriveIdentityState(token, role, photographerStatus) {
    if (!token) return "guest";
    if (role === "admin" || photographerStatus === "approved") return "verified_photographer";
    return "logged_in_unverified";
  },

  _tokenFingerprint(token) {
    if (!token) return "";
    return token.slice(-16);
  },

  _readIdentityCache(token) {
    try {
      const cache = wx.getStorageSync(IDENTITY_CACHE_KEY);
      if (!cache || typeof cache !== "object") return null;
      if (cache.tokenFingerprint !== this._tokenFingerprint(token)) return null;
      if (Date.now() - (cache.cachedAt || 0) > 1000 * 60 * 60 * 24 * 3) return null;
      return {
        role: cache.role || "",
        photographerStatus: cache.photographerStatus || "not_applied",
        rejectReason: cache.rejectReason || ""
      };
    } catch (_e) {
      return null;
    }
  },

  _writeIdentityCache(token, payload) {
    if (!token) return;
    wx.setStorageSync(IDENTITY_CACHE_KEY, {
      tokenFingerprint: this._tokenFingerprint(token),
      role: payload.role || "",
      photographerStatus: payload.photographerStatus || "not_applied",
      rejectReason: payload.rejectReason || "",
      cachedAt: Date.now()
    });
  },

  _clearIdentityCache() {
    wx.removeStorageSync(IDENTITY_CACHE_KEY);
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

  async loadAppointmentSummary() {
    const token = getToken();
    if (!token) {
      this.setData({
        appointmentSummary: {
          mineWaitingCustomerConfirm: 0,
          mineWaitingCompletionConfirm: 0,
          mineCompletedWithoutReview: 0,
          assignedPendingDecision: 0,
          assignedWaitingCustomerConfirm: 0,
          assignedWaitingCompletionMark: 0,
          minePendingTotal: 0,
          assignedPendingTotal: 0,
          centerPendingTotal: 0
        }
      });
      return;
    }
    try {
      const data = await request("/appointments/summary", { auth: true });
      const mineWaitingCustomerConfirm = data?.mine_waiting_customer_confirm || 0;
      const mineWaitingCompletionConfirm = data?.mine_waiting_completion_confirm || 0;
      const mineCompletedWithoutReview = data?.mine_completed_without_review || 0;
      const assignedPendingDecision = data?.assigned_pending_decision || 0;
      const assignedWaitingCustomerConfirm = data?.assigned_waiting_customer_confirm || 0;
      const assignedWaitingCompletionMark = data?.assigned_waiting_completion_mark || 0;
      this.setData({
        appointmentSummary: {
          mineWaitingCustomerConfirm,
          mineWaitingCompletionConfirm,
          mineCompletedWithoutReview,
          assignedPendingDecision,
          assignedWaitingCustomerConfirm,
          assignedWaitingCompletionMark,
          minePendingTotal: mineWaitingCustomerConfirm + mineWaitingCompletionConfirm + mineCompletedWithoutReview,
          assignedPendingTotal: assignedPendingDecision + assignedWaitingCustomerConfirm + assignedWaitingCompletionMark,
          centerPendingTotal:
            mineWaitingCustomerConfirm +
            mineWaitingCompletionConfirm +
            mineCompletedWithoutReview +
            assignedPendingDecision +
            assignedWaitingCustomerConfirm +
            assignedWaitingCompletionMark
        }
      });
      this.maybeShowAppointmentPrompt();
    } catch (_e) {
      this.setData({
        appointmentSummary: {
          mineWaitingCustomerConfirm: 0,
          mineWaitingCompletionConfirm: 0,
          mineCompletedWithoutReview: 0,
          assignedPendingDecision: 0,
          assignedWaitingCustomerConfirm: 0,
          assignedWaitingCompletionMark: 0,
          minePendingTotal: 0,
          assignedPendingTotal: 0,
          centerPendingTotal: 0
        }
      });
    }
  },

  maybeShowAppointmentPrompt() {
    if (this.data.identityState !== "verified_photographer") return;
    const pendingCount = this.data.appointmentSummary.assignedPendingDecision || 0;
    if (!pendingCount) return;
    const cacheValue = `${pendingCount}-${new Date().toISOString().slice(0, 10)}`;
    if (wx.getStorageSync(APPOINTMENT_PROMPT_CACHE_KEY) === cacheValue) return;
    wx.setStorageSync(APPOINTMENT_PROMPT_CACHE_KEY, cacheValue);
    wx.showModal({
      title: "收到新的预约申请",
      content: `现在有 ${pendingCount} 条预约待你处理，去预约中心看看吗？`,
      confirmText: "去处理",
      cancelText: "稍后再看",
      success: (res) => {
        if (!res.confirm) return;
        wx.navigateTo({ url: "/pages/appointments/index?tab=assigned" });
      }
    });
  },

  maybePromptPhotographerNotifications({
    token,
    role,
    photographerStatus,
    previousIdentityState,
    previousPhotographerStatus
  }) {
    const isApprovedPhotographer = role !== "admin" && photographerStatus === "approved";
    if (!token || !isApprovedPhotographer) return;
    const promptKey = `${this._tokenFingerprint(token)}:approved`;
    if (wx.getStorageSync(PHOTOGRAPHER_NOTIFY_PROMPT_KEY) === promptKey) return;

    const wasApprovedBefore =
      previousIdentityState === "verified_photographer" || previousPhotographerStatus === "approved";
    if (!wasApprovedBefore || this.data.identityState === "verified_photographer") {
      wx.setStorageSync(PHOTOGRAPHER_NOTIFY_PROMPT_KEY, promptKey);
      wx.showModal({
        title: "开启新预约提醒",
        content: "你已经通过入驻审核。开启后，有新预约时微信会第一时间提醒你。",
        confirmText: "去开启",
        cancelText: "稍后",
        success: (res) => {
          if (!res.confirm) return;
          this.enablePhotographerNotifications();
        }
      });
    }
  },

  async login() {
    this.setData({ loading: true });
    try {
      const t = await ensureLogin();
      this.setData({ token: t || "", identityLoading: true, identityState: "unknown" });
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
    clearAppointmentSubscribeCache();
    this._clearIdentityCache();
    this.setData({
      token: "",
      identityLoading: false,
      identityState: "guest",
      role: "",
      photographerStatus: "not_applied",
      rejectReason: "",
      membership: { isMember: false, expiresAt: "", loading: false }
    });
    this.syncViewState();
    wx.showToast({ title: "已退出", icon: "none" });
  },

  goEditPhotographerProfile() {
    if (!this.data.token) {
      wx.showToast({ title: "请先登录", icon: "none" });
      return;
    }
    if (this.data.photographerStatus !== "approved") {
      wx.showToast({ title: "入驻通过后可编辑", icon: "none" });
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
  },

  async goAppointmentCenter() {
    try {
      await ensureLogin();
      wx.navigateTo({ url: "/pages/appointments/index" });
    } catch (_e) {
      wx.showToast({ title: "请先登录", icon: "none" });
    }
  },

  async enablePhotographerNotifications() {
    if (this.data.notificationActionLoading) return;
    if (this.data.identityState !== "verified_photographer") {
      wx.showToast({ title: "通过入驻后可开启提醒", icon: "none" });
      return;
    }
    this.setData({ notificationActionLoading: true });
    try {
      await ensureLogin();
      await warmAppointmentSubscribeConfig();
      const result = await requestPhotographerAppointmentSubscriptions();
      const summary = summarizeAppointmentSubscribeResult(result);
      let title = "提醒申请已发起";
      if (summary === "accept") title = "已开启新预约提醒";
      else if (summary === "reject") title = "你这次没有开启提醒";
      else if (summary === "skipped") title = "当前暂无可用提醒模板";
      wx.showToast({ title, icon: "none" });
    } catch (e) {
      wx.showToast({ title: e?.message || "开启提醒失败", icon: "none" });
    } finally {
      this.setData({ notificationActionLoading: false });
    }
  }
});
