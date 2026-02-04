const { request } = require("../../utils/request");

Page({
  data: {
    lat: 31.2304,
    lng: 121.4737,
    loading: false,
    list: [],
    markers: []
  },

  async onLoad() {
    await this.refresh();
  },

  async refresh() {
    this.setData({ loading: true });
    try {
      const loc = await new Promise((resolve) => {
        wx.getLocation({
          type: "gcj02",
          success: resolve,
          fail: () => resolve(null)
        });
      });
      const lat = loc?.latitude || this.data.lat;
      const lng = loc?.longitude || this.data.lng;
      this.setData({ lat, lng });

      const list = await request("/photographers/nearby", {
        params: { lat, lng, radius_m: 8000, limit: 30 }
      });

      const markers = (list || []).map((p) => ({
        id: p.id,
        latitude: p.lat,
        longitude: p.lng,
        title: `#${p.id}`,
        width: 24,
        height: 24
      }));

      this.setData({ list: list || [], markers });
    } catch (e) {
      wx.showToast({ title: "加载失败", icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },

  onMarkerTap(e) {
    const id = e.markerId;
    wx.navigateTo({ url: `/pages/photographer/index?id=${id}` });
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/pages/photographer/index?id=${id}` });
  }
});

