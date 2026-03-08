module.exports = {
  // 推荐：真机调试使用 Cloudflare Tunnel（https）
  // 例如: "https://xxxx-xxxx.trycloudflare.com"
  API_BASE_URL: "https://mart-father-blogging-christine.trycloudflare.com",

  // 兜底：局域网直连模式
  DEV_API_HOST: "192.168.1.100",
  DEV_API_PORT: 8001,

  // 开发调试开关（生产请改为 false）
  ENABLE_DEV_TOOLS: true
};
