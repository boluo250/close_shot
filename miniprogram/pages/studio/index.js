const { request } = require("../../utils/request");
const { uploadImageToS3Like } = require("../../utils/upload");

function getStudioToken() {
  return wx.getStorageSync("studio_token") || "";
}
function setStudioToken(t) {
  wx.setStorageSync("studio_token", t);
}

Page({
  data: {
    username: "",
    password: "",
    token: "",
    uploading: false,
    loading: false,
    lastUrl: "",
    form: { title: "", tags: "" },
    items: []
  },

  onLoad() {
    const t = getStudioToken();
    this.setData({ token: t || "" });
    if (t) this.refresh();
  },

  onUser(e) {
    this.setData({ username: e.detail.value });
  },
  onPass(e) {
    this.setData({ password: e.detail.value });
  },
  onTitle(e) {
    this.setData({ "form.title": e.detail.value });
  },
  onTags(e) {
    this.setData({ "form.tags": e.detail.value });
  },

  async login() {
    try {
      const data = await request("/auth/login", {
        method: "POST",
        data: { username: this.data.username, password: this.data.password }
      });
      const t = data.access_token;
      setStudioToken(t);
      this.setData({ token: t });
      wx.showToast({ title: "已登录", icon: "none" });
      await this.refresh();
    } catch (e) {
      wx.showToast({ title: "登录失败", icon: "none" });
    }
  },

  logout() {
    setStudioToken("");
    this.setData({ token: "", items: [] });
  },

  async refresh() {
    if (!this.data.token) return;
    this.setData({ loading: true });
    try {
      const app = getApp();
      const base = app.globalData.apiBaseUrl;
      const data = await new Promise((resolve, reject) => {
        wx.request({
          url: base + "/studio/portfolio",
          method: "GET",
          header: { Authorization: "Bearer " + this.data.token },
          success: (res) => {
            if (res.statusCode >= 200 && res.statusCode < 300) resolve(res.data);
            else reject(new Error("failed"));
          },
          fail: reject
        });
      });
      const items = (data.items || []).map((x) => ({
        ...x,
        image_url: x.image_url && x.image_url.startsWith("/") ? base + x.image_url : x.image_url
      }));
      this.setData({ items });
    } catch (e) {
      wx.showToast({ title: "加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },

  async chooseAndUpload() {
    if (!this.data.token) {
      wx.showToast({ title: "请先登录", icon: "none" });
      return;
    }
    const choose = await new Promise((resolve) => {
      wx.chooseMedia({
        count: 1,
        mediaType: ["image"],
        sourceType: ["album", "camera"],
        success: resolve,
        fail: () => resolve(null)
      });
    });
    const file = choose?.tempFiles?.[0];
    if (!file) return;

    this.setData({ uploading: true });
    try {
      const up = await uploadImageToS3Like({
        tempFilePath: file.tempFilePath,
        filename: file.tempFilePath.split("/").pop() || "image.jpg",
        contentType: file.fileType ? `image/${file.fileType}` : "image/jpeg",
        prefix: "portfolio"
      });

      const app = getApp();
      const base = app.globalData.apiBaseUrl;
      const imageUrl = up.public_url || (up.proxy_url ? base + up.proxy_url : "");
      if (!imageUrl) throw new Error("no url");

      await new Promise((resolve, reject) => {
        wx.request({
          url: base + "/studio/portfolio",
          method: "POST",
          header: { Authorization: "Bearer " + this.data.token },
          data: {
            title: this.data.form.title,
            tags: this.data.form.tags,
            sort_order: 0,
            image_url: imageUrl
          },
          success: (res) => {
            if (res.statusCode >= 200 && res.statusCode < 300) resolve(true);
            else reject(new Error("failed"));
          },
          fail: reject
        });
      });

      this.setData({ lastUrl: imageUrl, "form.title": "", "form.tags": "" });
      wx.showToast({ title: "已创建作品", icon: "none" });
      await this.refresh();
    } catch (e) {
      wx.showToast({ title: "上传/创建失败", icon: "none" });
    } finally {
      this.setData({ uploading: false });
    }
  }
});

