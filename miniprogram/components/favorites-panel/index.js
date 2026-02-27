const { request } = require("../../utils/request");
const { normalizePhotographerCard } = require("../../utils/photographerCard");

Component({
  data: {
    loading: false,
    list: []
  },
  methods: {
    async refresh() {
      this.setData({ loading: true });
      try {
        const list = await request("/me/favorites", { auth: true });
        const app = getApp();
        const base = app.globalData.apiBaseUrl;
        const fixed = (list || []).map((p) => normalizePhotographerCard(p, base));

        this.setData({ list: fixed });
      } catch (e) {
        const msg = e?.message || "";
        const needLogin = msg.includes("Missing bearer token") || msg.includes("Invalid token");
        wx.showToast({ title: needLogin ? "请先登录" : "加载失败，请稍后重试", icon: "none" });
      } finally {
        this.setData({ loading: false });
      }
    }
  }
});

