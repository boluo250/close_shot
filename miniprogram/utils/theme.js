const STORAGE_KEY = "cs_theme_v1";

function normalizeTheme(t) {
  return t === "soda" ? "soda" : "classic";
}

function getTheme() {
  try {
    const v = wx.getStorageSync(STORAGE_KEY);
    return normalizeTheme(v || "classic");
  } catch (e) {
    return "classic";
  }
}

const listeners = new Set();

function subscribe(fn) {
  if (typeof fn !== "function") return () => {};
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function emit(theme) {
  listeners.forEach((fn) => {
    try {
      fn(theme);
    } catch (e) {
      // ignore
    }
  });
}

function getThemeClass(theme) {
  return theme === "soda" ? "cs-theme-soda" : "cs-theme-classic";
}

function applySystemUI(theme) {
  // 让导航栏/下拉背景更贴合主题（失败就忽略）
  const isSoda = theme === "soda";
  const backgroundColor = isSoda ? "#0b0d12" : "#ffffff";
  const frontColor = isSoda ? "#ffffff" : "#000000";
  try {
    if (typeof wx.setNavigationBarColor === "function") {
      wx.setNavigationBarColor({ backgroundColor, frontColor, animation: { duration: 120, timingFunc: "easeInOut" } });
    }
    if (typeof wx.setBackgroundColor === "function") {
      wx.setBackgroundColor({ backgroundColor });
    }
  } catch (e) {
    // ignore
  }
}

function setTheme(next) {
  const theme = normalizeTheme(next);
  try {
    wx.setStorageSync(STORAGE_KEY, theme);
  } catch (e) {
    // ignore
  }
  applySystemUI(theme);
  emit(theme);
  return theme;
}

module.exports = {
  STORAGE_KEY,
  getTheme,
  setTheme,
  subscribe,
  getThemeClass,
  applySystemUI
};

