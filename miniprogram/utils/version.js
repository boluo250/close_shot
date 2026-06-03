const env = require("../env");

const CHANNEL_LABELS = {
  release: "正式版",
  trial: "体验版",
  develop: "开发版"
};

function safeGetMiniProgramInfo() {
  try {
    if (typeof wx === "undefined" || typeof wx.getAccountInfoSync !== "function") return null;
    const accountInfo = wx.getAccountInfoSync();
    return accountInfo && accountInfo.miniProgram ? accountInfo.miniProgram : null;
  } catch (_e) {
    return null;
  }
}

function resolveChannelLabel(channel) {
  return CHANNEL_LABELS[channel] || "内部版";
}

function resolveVersionInfo() {
  const miniProgramInfo = safeGetMiniProgramInfo();
  const runtimeVersionName = (miniProgramInfo && miniProgramInfo.version) || "";
  const runtimeChannel = (miniProgramInfo && miniProgramInfo.envVersion) || "";
  const appName = env.APP_NAME || "Close Shot";
  const versionName = runtimeVersionName || env.APP_VERSION_NAME || "0.1.0";
  const channel = runtimeChannel || env.RELEASE_CHANNEL || "develop";
  const buildNo = env.APP_BUILD_NO || versionName;
  const channelLabel = resolveChannelLabel(channel);

  return {
    appName,
    versionName,
    versionText: `v${versionName}`,
    buildNo,
    buildText: `Build ${buildNo}`,
    channel,
    channelLabel,
    showBuildMeta: channel !== "release",
    fullText: `${appName} v${versionName} · ${channelLabel} · Build ${buildNo}`
  };
}

module.exports = {
  resolveVersionInfo
};
