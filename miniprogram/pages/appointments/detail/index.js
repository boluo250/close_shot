const { ensureLogin } = require("../../../utils/auth");
const { request } = require("../../../utils/request");

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
    id: null,
    mode: "mine",
    loading: false,
    item: null
  },

  onLoad(query) {
    this.setData({
      id: Number(query.id || 0),
      mode: query.mode === "assigned" ? "assigned" : "mine"
    });
  },

  onShow() {
    this.load();
  },

  async load() {
    if (!this.data.id) return;
    this.setData({ loading: true });
    try {
      await ensureLogin();
      const item = await request(`/appointments/${this.data.id}`, { auth: true });
      this.setData({
        item: {
          ...item,
          statusLabel: formatStatus(item.status),
          scheduledText: formatTime(item.scheduled_at)
        }
      });
    } catch (e) {
      wx.showToast({ title: e?.message || "加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },

  async postAction(path, successText) {
    try {
      await request(path, { method: "POST", auth: true, data: {} });
      wx.showToast({ title: successText, icon: "none" });
      this.load();
    } catch (err) {
      wx.showToast({ title: err?.message || "操作失败", icon: "none" });
    }
  },

  handleAccept() {
    this.postAction(`/appointments/${this.data.id}/accept`, "已同意预约");
  },

  handleReject() {
    this.postAction(`/appointments/${this.data.id}/reject`, "已拒绝预约");
  },

  handleConfirm() {
    this.postAction(`/appointments/${this.data.id}/confirm`, "已确认预约");
  },

  handleCancel() {
    this.postAction(`/appointments/${this.data.id}/cancel`, "已取消预约");
  },

  handleComplete() {
    this.postAction(`/appointments/${this.data.id}/complete`, "状态已更新");
  },

  handleReview() {
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
              await request(`/appointments/${this.data.id}/review`, {
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
