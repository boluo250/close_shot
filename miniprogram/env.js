module.exports = {
  // 真机必须使用已备案/已配置到 request 合法域名的 HTTPS 地址，不能用裸 IP 或 HTTP
  API_BASE_URL: "https://bianpai.xyz",

  // 兜底：局域网直连模式
  DEV_API_HOST: "192.168.1.100",
  DEV_API_PORT: 8001,

  // 开发调试开关（生产请改为 false）
  ENABLE_DEV_TOOLS: true
};
