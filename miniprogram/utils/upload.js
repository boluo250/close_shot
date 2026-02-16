const { request } = require("./request");

function _safeName(name) {
  return (name || "file").replace(/[^\w.\-]+/g, "-");
}

async function presign(filename, contentType, prefix) {
  return await request("/upload/presign", {
    method: "POST",
    data: { filename: _safeName(filename), content_type: contentType || null, prefix: prefix || "uploads" }
  });
}

async function uploadImageToS3Like({ tempFilePath, filename, contentType, prefix }) {
  const presignRes = await presign(filename, contentType, prefix);
  // 兼容 local backend：presign 可能返回相对路径，需要拼接后端 base URL
  const app = getApp();
  const base = app.globalData.apiBaseUrl;
  const putUrl =
    typeof presignRes.url === "string" && presignRes.url.startsWith("/") ? base + presignRes.url : presignRes.url;
  const fs = wx.getFileSystemManager();
  const buffer = await new Promise((resolve, reject) => {
    fs.readFile({
      filePath: tempFilePath,
      success: (r) => resolve(r.data),
      fail: reject
    });
  });

  await new Promise((resolve, reject) => {
    wx.request({
      url: putUrl,
      method: "PUT",
      header: presignRes.headers || {},
      data: buffer,
      success: (r) => {
        if (r.statusCode >= 200 && r.statusCode < 300) resolve(true);
        else reject(new Error("PUT failed"));
      },
      fail: reject
    });
  });

  return presignRes; // 含 public_url / proxy_url / object_key
}

module.exports = { uploadImageToS3Like };

