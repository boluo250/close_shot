const { request } = require("./request");

const IMAGE_CONTENT_TYPE_MAP = {
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  webp: "image/webp",
  heic: "image/heic",
  heif: "image/heif"
};

function _safeName(name) {
  return (name || "file").replace(/[^\w.\-]+/g, "-");
}

function _contentTypeFromFilename(name) {
  const safeName = _safeName(name || "");
  const match = safeName.match(/\.([^.]+)$/);
  if (!match) return "";
  return IMAGE_CONTENT_TYPE_MAP[(match[1] || "").toLowerCase()] || "";
}

function _resolveImageContentType(filename, providedType) {
  const normalized = String(providedType || "")
    .trim()
    .toLowerCase();

  if (normalized === "image/jpg") return "image/jpeg";
  if (normalized.startsWith("image/") && IMAGE_CONTENT_TYPE_MAP[normalized.slice(6)]) {
    return IMAGE_CONTENT_TYPE_MAP[normalized.slice(6)];
  }
  if (IMAGE_CONTENT_TYPE_MAP[normalized]) {
    return IMAGE_CONTENT_TYPE_MAP[normalized];
  }

  const inferred = _contentTypeFromFilename(filename);
  if (normalized === "image" || normalized === "image/*" || normalized === "image/image") {
    return inferred || "image/jpeg";
  }
  if (normalized.startsWith("image/")) {
    return inferred || normalized;
  }
  return inferred || "image/jpeg";
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
  const resolvedContentType = _resolveImageContentType(filename || uploadPath, contentType);
  const presignRes = await presign(filename, resolvedContentType, prefix);
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
