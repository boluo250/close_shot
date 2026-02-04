const { getToken, ensureLogin } = require("./auth");

function request(path, { method = "GET", data = null, params = null, auth = false } = {}) {
  const app = getApp();
  const base = app.globalData.apiBaseUrl;

  return new Promise(async (resolve, reject) => {
    try {
      let url = base + path;
      if (params) {
        const qs = Object.keys(params)
          .filter((k) => params[k] !== undefined && params[k] !== null && params[k] !== "")
          .map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`)
          .join("&");
        if (qs) url += (url.includes("?") ? "&" : "?") + qs;
      }

      let token = getToken();
      if (auth && !token) token = await ensureLogin();

      wx.request({
        url,
        method,
        data,
        header: auth && token ? { Authorization: "Bearer " + token } : {},
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) resolve(res.data);
          else reject(new Error(res.data?.detail || "request failed"));
        },
        fail: reject
      });
    } catch (e) {
      reject(e);
    }
  });
}

module.exports = { request };

