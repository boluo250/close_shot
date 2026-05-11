const { request } = require("./request");

function _safeName(name) {
  return (name || "file").replace(/[^\w.\-]+/g, "-");
}

async function presign(filename, contentType, prefix) {
  return await request("/upload/presign", {
    method: "POST",
    data: { filename: _safeName(filename), content_type: contentType || null, prefix: prefix || "uploads" },
    auth: true
  });
}

async function _getFileSize(filePath) {
  return await new Promise((resolve) => {
    wx.getFileInfo({
      filePath,
      success: (res) => resolve(Number(res.size) || 0),
      fail: () => resolve(0)
    });
  });
}

async function _compressImage(filePath, quality) {
  return await new Promise((resolve) => {
    wx.compressImage({
      src: filePath,
      quality,
      success: (res) => resolve(res.tempFilePath || filePath),
      fail: () => resolve(filePath)
    });
  });
}

async function _prepareUploadPath(tempFilePath, compress) {
  const cfg = compress === false ? null : { maxSizeKB: 700, quality: 72, ...(compress || {}) };
  if (!cfg || typeof wx.compressImage !== "function") return tempFilePath;

  const originalSize = await _getFileSize(tempFilePath);
  if (!originalSize) return tempFilePath;
  if (originalSize <= cfg.maxSizeKB * 1024) return tempFilePath;

  const compressedPath = await _compressImage(tempFilePath, cfg.quality);
  if (!compressedPath || compressedPath === tempFilePath) return tempFilePath;
  const compressedSize = await _getFileSize(compressedPath);
  if (!compressedSize) return tempFilePath;
  return compressedSize < originalSize ? compressedPath : tempFilePath;
}

async function uploadImageToS3Like({ tempFilePath, filename, contentType, prefix, compress }) {
  const uploadPath = await _prepareUploadPath(tempFilePath, compress);
  const presignRes = await presign(filename, contentType, prefix);
  // 兼容 local backend：presign 可能返回相对路径，需要拼接后端 base URL
  const app = getApp();
  const base = app.globalData.apiBaseUrl;
  const putUrl =
    typeof presignRes.url === "string" && presignRes.url.startsWith("/") ? base + presignRes.url : presignRes.url;
  const fs = wx.getFileSystemManager();
  const buffer = await new Promise((resolve, reject) => {
    fs.readFile({
      filePath: uploadPath,
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
