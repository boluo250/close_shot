const FIXED_THEME = "soda";
const STORAGE_KEY = "cs_theme_v1";

function getTheme() {
  return FIXED_THEME;
}

function subscribe(_fn) {
  return () => {};
}

function getThemeClass() {
  return "cs-theme-soda";
}

function applySystemUI() {
  try {
    if (typeof wx.setNavigationBarColor === "function") {
      wx.setNavigationBarColor({
        backgroundColor: "#0b0d12",
        frontColor: "#ffffff",
        animation: { duration: 120, timingFunc: "easeInOut" }
      });
    }
    if (typeof wx.setBackgroundColor === "function") {
      wx.setBackgroundColor({ backgroundColor: "#0b0d12" });
    }
  } catch (e) {
    // ignore
  }
}

function setTheme() {
  applySystemUI();
  return FIXED_THEME;
}

module.exports = {
  FIXED_THEME,
  STORAGE_KEY,
  getTheme,
  setTheme,
  subscribe,
  getThemeClass,
  applySystemUI
};
