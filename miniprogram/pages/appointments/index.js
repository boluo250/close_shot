const { ensureLogin } = require("../../utils/auth");
const { request } = require("../../utils/request");

function formatStatus(status) {
  return (
    {
      pending: "待摄影师确认",
      accepted_pending_customer: "待你确认预约",
      confirmed: "已确认预约",
      rejected: "已拒绝",
      completed: "已完成",
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
    mode: "mine",
    items: [],
    loading: false
  },

  onLoad(query) {
    const mode = query.mode === "assigned" ? "assigned" : "mine";
    this.setData({ mode });
    wx.setNavigationBarTitle({ title: mode === "assigned" ? "预约工作台" : "我的预约" });
  },

  onShow() {
    this.load();
  },

  async load() {
    this.setData({ loading: true });
    try {
      await ensureLogin();
      const path = this.data.mode === "assigned" ? "/appointments/assigned" : "/appointments/mine";
      const data = await request(path, { auth: true });
      const items = Array.isArray(data?.items)
        ? data.items.map((item) => ({
            ...item,
            statusLabel: formatStatus(item.status),
            scheduledText: formatTime(item.scheduled_at),
            counterpartyName:
              this.data.mode === "assigned"
                ? item.customer_display_name || `客户 #${item.customer_user_id}`
                : item.photographer_display_name || `摄影师 #${item.photographer_id}`
          }))
        : [];
      this.setData({ items });
    } catch (e) {
      wx.showToast({ title: e?.message || "加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id;
    if (!id) return;
    wx.navigateTo({ url: `/pages/appointments/detail/index?id=${id}&mode=${this.data.mode}` });
  }
});
