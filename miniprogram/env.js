module.exports = {
  APP_NAME: "边拍",
  // 对外展示版本号，建议使用 major.minor.patch
  APP_VERSION_NAME: "3.1.0",
  // 内部构建号，建议使用 yyyymmdd.seq，方便排障定位具体发版包
  APP_BUILD_NO: "20260603.1",
  RELEASE_CHANNEL: "release",

  // 真机必须使用已备案/已配置到 request 合法域名的 HTTPS 地址，不能用裸 IP 或 HTTP
  API_BASE_URL: "https://bianpai.xyz",

  // 兜底：局域网直连模式
  DEV_API_HOST: "192.168.1.100",
  DEV_API_PORT: 8001,

  // 开发调试开关（生产请改为 false）
  ENABLE_DEV_TOOLS: true
};
