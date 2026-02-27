function getToken() {
  return wx.getStorageSync("token") || "";
}

function setToken(token) {
  if (token) wx.setStorageSync("token", token);
  else wx.removeStorageSync("token");
}

function clearAuthState() {
  // 清理登录态与认证工作台草稿，避免账号切换/删号后看到旧数据
  wx.removeStorageSync("token");
  wx.removeStorageSync("studio_draft_v1");
}

async function ensureLogin() {
  const token = getToken();
  if (token) return token;

  const { code } = await new Promise((resolve, reject) => {
    wx.login({
      success: resolve,
      fail: reject
    });
  });
  if (!code) throw new Error("微信登录凭证为空");

  const app = getApp();
  const base = app.globalData.apiBaseUrl;
  const res = await new Promise((resolve, reject) => {
    wx.request({
      url: base + "/auth/wechat",
      method: "POST",
      data: { code },
      success: resolve,
      fail: reject
    });
  });

  if (res.statusCode >= 200 && res.statusCode < 300) {
    const t = res.data.access_token;
    setToken(t);
    return t;
  }
  throw new Error(res.data?.detail || "微信登录失败");
}

module.exports = { getToken, setToken, ensureLogin, clearAuthState };

