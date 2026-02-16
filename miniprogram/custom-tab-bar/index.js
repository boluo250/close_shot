const theme = require("../utils/theme");

Component({
  data: {
    selected: 0,
    color: "#8a8f98",
    // 选中态用主题绿，和「我要拍照」一致
    selectedColor: "#bfe84a",
    themeClass: "cs-theme-classic",
    list: [
      { key: "nearby", pagePath: "pages/map/index", text: "附近", icon: "⌖" },
      { key: "fav", pagePath: "pages/favorites/index", text: "收藏", icon: "♡" },
      // “我的”用自绘线性图标，避免彩色 emoji 风格不统一
      { key: "mine", pagePath: "pages/mine/index", text: "我的", icon: "" }
    ]
  },
  lifetimes: {
    attached() {
      const t = theme.getTheme();
      this.setData({
        themeClass: theme.getThemeClass(t),
        color: t === "soda" ? "rgba(148, 163, 184, 0.85)" : "#8a8f98",
        selectedColor: t === "soda" ? "#39ff88" : "#bfe84a"
      });
      this._unsubTheme = theme.subscribe((next) => {
        this.setData({
          themeClass: theme.getThemeClass(next),
          color: next === "soda" ? "rgba(148, 163, 184, 0.85)" : "#8a8f98",
          selectedColor: next === "soda" ? "#39ff88" : "#bfe84a"
        });
      });
    },
    detached() {
      if (this._unsubTheme) this._unsubTheme();
    }
  },
  methods: {
    onChange(e) {
      const { index, path } = e.currentTarget.dataset;
      const url = "/" + path;
      wx.switchTab({ url });
      this.setData({ selected: Number(index) });
    }
  }
});

