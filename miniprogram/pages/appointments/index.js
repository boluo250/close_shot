const { ensureLogin } = require("../../utils/auth");
const { request } = require("../../utils/request");

function formatStatus(item, tab = "mine") {
  const status = item?.status;
  if (status === "confirmed" && item?.photographer_completed_at && !item?.customer_completed_at) {
    return tab === "assigned" ? "已完成订单" : "待评价";
  }
  if (tab === "mine" && status === "completed" && item?.can_review) {
    return "待评价";
  }
  return (
    {
      pending: "待摄影师确认",
      accepted_pending_customer: tab === "assigned" ? "待客户最终确认" : "待你确认预约",
      confirmed: "已确认预约",
      rejected: "已拒绝",
      completed: "已完成订单",
      cancelled: "已取消"
    }[status] || status || "未知状态"
  );
}

function formatTime(text) {
  if (!text) return "";
  const dt = new Date(text);
  if (Number.isNaN(dt.getTime())) return text;
  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, "0");
  const d = String(dt.getDate()).padStart(2, "0");
  const hh = String(dt.getHours()).padStart(2, "0");
  const mm = String(dt.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${d} ${hh}:${mm}`;
}

Page({
  data: {
    activeTab: "mine",
    loading: false,
    isPhotographer: false,
    mineItems: [],
    assignedItems: [],
    displayItems: [],
    summary: {
      minePendingTotal: 0,
      assignedPendingTotal: 0,
      mineWaitingCustomerConfirm: 0,
      mineWaitingCompletionConfirm: 0,
      mineCompletedWithoutReview: 0,
      assignedPendingDecision: 0,
      assignedWaitingCustomerConfirm: 0,
      assignedWaitingCompletionMark: 0
    }
  },

  onLoad(query) {
    const activeTab = query.tab === "assigned" || query.mode === "assigned" ? "assigned" : "mine";
    this.setData({ activeTab });
    wx.setNavigationBarTitle({ title: "预约中心" });
  },

  onShow() {
    this.load();
  },

  async load() {
    this.setData({ loading: true });
    try {
      await ensureLogin();
      const identity = await request("/me/identity", { auth: true });
      const isPhotographer = identity?.role === "admin" || identity?.photographer_status === "approved";
      const [mineData, summaryData, assignedData] = await Promise.all([
        request("/appointments/mine", { auth: true }),
        request("/appointments/summary", { auth: true }),
        isPhotographer ? request("/appointments/assigned", { auth: true }) : Promise.resolve({ items: [] })
      ]);
      const summary = {
        mineWaitingCustomerConfirm: summaryData?.mine_waiting_customer_confirm || 0,
        mineWaitingCompletionConfirm: summaryData?.mine_waiting_completion_confirm || 0,
        mineCompletedWithoutReview: summaryData?.mine_completed_without_review || 0,
        assignedPendingDecision: summaryData?.assigned_pending_decision || 0,
        assignedWaitingCustomerConfirm: summaryData?.assigned_waiting_customer_confirm || 0,
        assignedWaitingCompletionMark: summaryData?.assigned_waiting_completion_mark || 0,
        minePendingTotal:
          (summaryData?.mine_waiting_customer_confirm || 0) +
          (summaryData?.mine_waiting_completion_confirm || 0) +
          (summaryData?.mine_completed_without_review || 0),
        assignedPendingTotal:
          (summaryData?.assigned_pending_decision || 0) +
          (summaryData?.assigned_waiting_customer_confirm || 0) +
          (summaryData?.assigned_waiting_completion_mark || 0)
      };
      const mineItems = this.decorateItems(mineData?.items, "mine");
      const assignedItems = this.decorateItems(assignedData?.items, "assigned");
      const activeTab = !isPhotographer && this.data.activeTab === "assigned" ? "mine" : this.data.activeTab;
      this.setData({
        isPhotographer,
        mineItems,
        assignedItems,
        summary,
        activeTab
      }, () => this.syncDisplayItems());
    } catch (e) {
      wx.showToast({ title: e?.message || "加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },

  decorateItems(items, tab) {
    if (!Array.isArray(items)) return [];
    return items.map((item) => ({
      ...item,
      statusLabel: formatStatus(item, tab),
      scheduledText: formatTime(item.scheduled_at),
      counterpartyName:
        tab === "assigned"
          ? item.customer_display_name || `客户 #${item.customer_user_id}`
          : item.photographer_display_name || `摄影师 #${item.photographer_id}`
    }));
  },

  syncDisplayItems() {
    const displayItems = this.data.activeTab === "assigned" ? this.data.assignedItems : this.data.mineItems;
    this.setData({ displayItems });
  },

  switchTab(e) {
    const tab = e.currentTarget.dataset.tab;
    if (!tab || tab === this.data.activeTab) return;
    if (tab === "assigned" && !this.data.isPhotographer) return;
    this.setData({ activeTab: tab }, () => this.syncDisplayItems());
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/pages/appointments/detail/index?id=${id}&mode=${this.data.activeTab}` });
  }
});
