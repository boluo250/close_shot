const { getToken, ensureLogin, clearAuthState } = require("./auth");

function formatErrorDetail(detail) {
  if (!detail) return "request failed";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (!item || typeof item !== "object") return "";
        const loc = Array.isArray(item.loc)
          ? item.loc.filter((part) => part !== "body").join(".")
          : "";
        const msg = item.msg || item.message || "";
        if (loc && msg) return `${loc}：${msg}`;
        return msg || "";
      })
      .filter(Boolean);
    return parts.join("；") || "request failed";
  }
  if (typeof detail === "object") {
    return detail.message || detail.msg || JSON.stringify(detail);
  }
  return String(detail);
}

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

      // 登录态过期/删号后自动清理缓存并重登一次，避免入驻中心显示旧状态
      if (auth && res.statusCode === 401) {
        clearAuthState();
        token = await ensureLogin();
        res = await sendRequest(token);
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }
      }

      reject(new Error(formatErrorDetail(res.data?.detail)));
    } catch (e) {
      reject(e);
    }
  });
}

module.exports = { request };
