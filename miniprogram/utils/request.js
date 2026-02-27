const { getToken, ensureLogin, clearAuthState } = require("./auth");

function request(path, { method = "GET", data = null, params = null, auth = false } = {}) {
  const app = getApp();
  const base = app.globalData.apiBaseUrl;
  let url = base + path;
  if (params) {
    const qs = Object.keys(params)
      .filter((k) => params[k] !== undefined && params[k] !== null && params[k] !== "")
      .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
      .join("&");
    if (qs) url += (url.includes("?") ? "&" : "?") + qs;
  }

  const sendRequest = (token) =>
    new Promise((resolve, reject) => {
      wx.request({
        url,
        method,
        data,
        header: auth && token ? { Authorization: "Bearer " + token } : {},
        success: resolve,
        fail: reject
      });
    });

  return new Promise(async (resolve, reject) => {
    try {
      let token = getToken();
      if (auth && !token) token = await ensureLogin();

      let res = await sendRequest(token);
      if (res.statusCode >= 200 && res.statusCode < 300) {
        resolve(res.data);
        return;
      }

      // 登录态过期/删号后自动清理缓存并重登一次，避免认证中心显示旧状态
      if (auth && res.statusCode === 401) {
        clearAuthState();
        token = await ensureLogin();
        res = await sendRequest(token);
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
      }

      reject(new Error(res.data?.detail || "request failed"));
    } catch (e) {
      reject(e);
    }
  });
}

module.exports = { request };

