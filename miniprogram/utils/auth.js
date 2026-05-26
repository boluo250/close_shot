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

function formatWechatLoginError(detail, statusCode) {
  const text = typeof detail === "string" ? detail : "";
  if (text.includes("missing WECHAT_APPID/WECHAT_SECRET")) {
    return "服务端未配置微信登录，请补全 WECHAT_APPID / WECHAT_SECRET";
  }
  if (text.includes("wechat login failed:")) {
    return `微信登录失败：${text.replace("wechat login failed:", "").trim() || "请检查 AppID / AppSecret"}`;
  }
  if (text.includes("wechat login response missing openid/session_key")) {
    return "微信登录返回异常，未拿到 openid/session_key";
  }
  if (text.includes("wechat login request failed")) {
    return "微信登录请求失败，请检查服务端网络";
  }
  if (statusCode === 401) {
    return "登录已失效，请重新登录";
  }
  return text || "微信登录失败";
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
    if (!t) {
      clearAuthState();
      throw new Error("微信登录成功但服务端未返回 access_token");
    }
    setToken(t);
    return t;
  }
  clearAuthState();
  throw new Error(formatWechatLoginError(res.data?.detail, res.statusCode));
}

module.exports = { getToken, setToken, ensureLogin, clearAuthState };
