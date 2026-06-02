Page({
  onShow() {
    const panel = this.selectComponent("#minePanel");
    if (panel && typeof panel.refresh === "function") {
      panel.refresh();
    }
  }
});
