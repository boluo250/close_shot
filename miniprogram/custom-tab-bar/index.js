Component({
  data: {
    selected: 0,
    color: "rgba(148, 163, 184, 0.85)",
    selectedColor: "#39ff88",
    themeClass: "cs-theme-soda",
    list: [
      { key: "nearby", pagePath: "pages/map/index", text: "附近", icon: "⌖" },
      { key: "fav", pagePath: "pages/favorites/index", text: "收藏", icon: "♡" },
      // “我的”用自绘线性图标，避免彩色 emoji 风格不统一
      { key: "mine", pagePath: "pages/mine/index", text: "我的", icon: "" }
    ]
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
