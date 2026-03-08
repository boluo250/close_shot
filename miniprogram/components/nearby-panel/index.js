const { request } = require("../../utils/request");
const { normalizePhotographerCard } = require("../../utils/photographerCard");

Component({
  data: {
    lat: 31.2304,
    lng: 121.4737,
    cityText: "定位中",
    loading: false,
    errorText: "",
    list: [],
    markers: [],
    circles: [],
    selected: null,
    activeTag: ""
  },
  lifetimes: {
    attached() {
      this.refresh();
    }
  },
  methods: {
    async refresh() {
      this.setData({ loading: true, errorText: "" });
      try {
        const loc = await new Promise((resolve) => {
          let done = false;
          const timer = setTimeout(() => {
            if (done) return;
            done = true;
            resolve(null);
          }, 2000);
          wx.getLocation({
            type: "gcj02",
            success: (res) => {
              if (done) return;
              done = true;
              clearTimeout(timer);
              resolve(res);
            },
            fail: () => {
              if (done) return;
              done = true;
              clearTimeout(timer);
              resolve(null);
            }
          });
        });
        const lat = loc?.latitude || this.data.lat;
        const lng = loc?.longitude || this.data.lng;
        this.setData({ lat, lng });

        const list = await request("/photographers/nearby", {
          params: {
            lat,
            lng,
            max_distance_m: 50000,
            limit: 20,
            tag: this.data.activeTag || undefined
          }
        });

        const app = getApp();
        const base = app.globalData.apiBaseUrl;

        const fixed = (list || []).map((p) => normalizePhotographerCard(p, base));
        const withMapAvatarStyle = (url) => {
          if (!url || typeof url !== "string") return "";
          if (!url.startsWith("http://") && !url.startsWith("https://")) return url;
          if (!url.includes("/media/")) {
            return `${base}/media/styled/avatar?style=map_avatar&v=2&url=${encodeURIComponent(url)}`;
          }
          const sep = url.includes("?") ? "&" : "?";
          return `${url}${sep}style=map_avatar&v=2`;
        };

        const markers = fixed.map((p) => {
          const marker = {
            id: p.id,
            latitude: p.service_center_lat,
            longitude: p.service_center_lng,
            title: p.display_name || `#${p.id}`,
            width: 36,
            height: 36
          };
          if (p.avatar_url && (p.avatar_url.startsWith("http://") || p.avatar_url.startsWith("https://"))) {
            marker.iconPath = withMapAvatarStyle(p.avatar_url);
          } else {
            marker.label = {
              content: (p.display_name || "摄影师").slice(0, 1),
              color: "#111827",
              bgColor: "#ffffff",
              borderRadius: 999,
              padding: 6,
              textAlign: "center",
              anchorX: 0,
              anchorY: -42
            };
          }
          return marker;
        });

        this.setData({
          cityText: "已定位",
          list: fixed,
          markers,
          circles: [],
          selected: null
        });
      } catch (e) {
        const msg = e?.message || "加载失败";
        this.setData({ errorText: msg });
        wx.showToast({ title: msg.slice(0, 15), icon: "none" });
      } finally {
        this.setData({ loading: false });
      }
    },

    onMarkerTap(e) {
      const id = e.markerId;
      const p = (this.data.list || []).find((x) => x.id === id);
      if (!p) return;
      const distance = encodeURIComponent(p.distanceCopy || "");
      wx.navigateTo({ url: `/pages/photographer/index?id=${id}&distance=${distance}&from=nearby` });
    },

    onTapCity() {
      wx.showModal({
        title: "定位/切换城市",
        content: "MVP：这里后续可接入城市选择或重新定位。",
        showCancel: false
      });
    },

  }
});

