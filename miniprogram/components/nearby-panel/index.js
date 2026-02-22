const { request } = require("../../utils/request");

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

        const fixed = (list || []).map((p) => {
          const displayName = p.display_name || `摄影师 #${p.id}`;
          const avatarUrl =
            p.avatar_url && p.avatar_url.startsWith("/") ? base + p.avatar_url : p.avatar_url || "";
          const preview = Array.isArray(p.preview_image_urls) ? p.preview_image_urls : [];
          const previewFixed = preview
            .map((u) => (u && u.startsWith("/") ? base + u : u))
            .filter(Boolean);
          const portfolioCount =
            typeof p.portfolio_count === "number" ? p.portfolio_count : previewFixed.length;
          const rateHourMin =
            typeof p.rate_hour_min_cents === "number" ? Math.round(p.rate_hour_min_cents / 100) : "";
          const rateItemMin =
            typeof p.rate_item_min_cents === "number" ? Math.round(p.rate_item_min_cents / 100) : "";
          const rateParts = [];
          if (rateHourMin) rateParts.push(`¥${rateHourMin}/小时起`);
          if (rateItemMin) rateParts.push(`¥${rateItemMin}/张起`);

          const distanceCopy =
            p.distance_copy != null && p.distance_copy !== ""
              ? p.distance_copy
              : p.distance_km != null
                ? (p.distance_km < 1 ? "约 <1 km" : `约 ${Number(p.distance_km).toFixed(1)} km`)
                : "";
          return {
            ...p,
            display_name: displayName,
            avatar_url: avatarUrl,
            distance_copy: distanceCopy,
            starting_price_yuan:
              typeof p.starting_price_cents === "number"
                ? Math.round(p.starting_price_cents / 100)
                : "",
            preview_image_urls: previewFixed,
            preview_count: previewFixed.length,
            preview_empty: previewFixed.length === 0,
            portfolio_count: portfolioCount,
            rate_hour_min_yuan: rateHourMin,
            rate_item_min_yuan: rateItemMin,
            rate_copy: rateParts.join(" · ")
          };
        });

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
            marker.iconPath = p.avatar_url;
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
      wx.navigateTo({ url: `/pages/photographer/index?id=${id}` });
    },

    goDetail(e) {
      const id = e.currentTarget.dataset.id;
      wx.navigateTo({ url: `/pages/photographer/index?id=${id}` });
    },

    onTapCity() {
      wx.showModal({
        title: "定位/切换城市",
        content: "MVP：这里后续可接入城市选择或重新定位。",
        showCancel: false
      });
    },

    onTapSearch() {
      wx.showToast({ title: "搜索入口后续接入", icon: "none" });
    },

    onShootCTA() {
      wx.showActionSheet({
        itemList: ["情侣", "闺蜜", "个人", "清空筛选"],
        success: async (res) => {
          const idx = res.tapIndex;
          const tag = idx === 0 ? "情侣" : idx === 1 ? "闺蜜" : idx === 2 ? "个人" : "";
          this.setData({ activeTag: tag });
          await this.refresh();
        }
      });
    }
  }
});

