const { ensureLogin } = require("../../utils/auth");
const { request } = require("../../utils/request");

function formatStatus(status) {
  return (
    {
      pending: "待摄影师确认",
      accepted: "已接单",
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

  async handleAccept(e) {
    const id = e.currentTarget.dataset.id;
    try {
      await request(`/appointments/${id}/accept`, { method: "POST", data: {}, auth: true });
      wx.showToast({ title: "已接单", icon: "none" });
      this.load();
    } catch (err) {
      wx.showToast({ title: err?.message || "操作失败", icon: "none" });
    }
  },

  async handleReject(e) {
    const id = e.currentTarget.dataset.id;
    try {
      await request(`/appointments/${id}/reject`, { method: "POST", data: {}, auth: true });
      wx.showToast({ title: "已拒绝", icon: "none" });
      this.load();
    } catch (err) {
      wx.showToast({ title: err?.message || "操作失败", icon: "none" });
    }
  },

  async handleCancel(e) {
    const id = e.currentTarget.dataset.id;
    try {
      await request(`/appointments/${id}/cancel`, { method: "POST", data: {}, auth: true });
      wx.showToast({ title: "已取消", icon: "none" });
      this.load();
    } catch (err) {
      wx.showToast({ title: err?.message || "操作失败", icon: "none" });
    }
  },

  async handleComplete(e) {
    const id = e.currentTarget.dataset.id;
    try {
      await request(`/appointments/${id}/complete`, { method: "POST", auth: true });
      wx.showToast({ title: "已确认完成", icon: "none" });
      this.load();
    } catch (err) {
      wx.showToast({ title: err?.message || "操作失败", icon: "none" });
    }
  },

  handleReview(e) {
    const id = e.currentTarget.dataset.id;
    const options = ["5 分", "4 分", "3 分", "2 分", "1 分"];
    wx.showActionSheet({
      itemList: options,
      success: ({ tapIndex }) => {
        const rating = 5 - Number(tapIndex || 0);
        wx.showModal({
          title: "填写评价",
          editable: true,
          placeholderText: "可选，写下本次拍摄体验",
          success: async (res) => {
            if (!res.confirm) return;
            try {
              await request(`/appointments/${id}/review`, {
                method: "POST",
                auth: true,
                data: {
                  rating,
                  content: res.content || ""
                }
              });
              wx.showToast({ title: "评价已提交", icon: "none" });
              this.load();
            } catch (err) {
              wx.showToast({ title: err?.message || "提交失败", icon: "none" });
            }
          }
        });
      }
    });
  }
});
