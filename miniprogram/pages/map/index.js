const { request } = require("../../utils/request");
const { trackBatch } = require("../../utils/analytics");

Page({
  data: {
    lat: 31.2304,
    lng: 121.4737,
    scale: 14,
    cityText: "定位中",
    loading: false,
    errorText: "",
    list: [],
    markers: [],
    circles: [],
    selected: null,
    activeTag: "",
    searchRadiusM: 5000,
    markerOverflow: false
  },

  async onLoad() {
    this.mapCtx = wx.createMapContext("map", this);
    this._exposureSet = new Set();
    await this.refresh();
  },

  onShow() {
    // 返回或切回页面时刷新附近摄影师
    if (!this.data.loading) {
      this.refresh();
    }
  },

  async onPullDownRefresh() {
    await this.refresh();
    wx.stopPullDownRefresh();
  },

  onUnload() {
    if (this._regionDebounceTimer) {
      clearTimeout(this._regionDebounceTimer);
      this._regionDebounceTimer = null;
    }
  },

  async getCurrentLocation() {
    return await new Promise((resolve) => {
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
  },

  haversineDistanceM(lat1, lng1, lat2, lng2) {
    const toRad = (v) => (v * Math.PI) / 180;
    const earthRadius = 6371000;
    const dLat = toRad(lat2 - lat1);
    const dLng = toRad(lng2 - lng1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * earthRadius * Math.asin(Math.sqrt(a));
  },

  async refresh(options = {}) {
    this.setData({ loading: true, errorText: "" });
    try {
      let lat = typeof options.lat === "number" ? options.lat : null;
      let lng = typeof options.lng === "number" ? options.lng : null;
      let searchRadiusM =
        typeof options.maxDistanceM === "number" ? options.maxDistanceM : this.data.searchRadiusM || 5000;
      if (lat === null || lng === null) {
        const loc = await this.getCurrentLocation();
        lat = loc?.latitude || this.data.lat;
        lng = loc?.longitude || this.data.lng;
      }
      searchRadiusM = Math.max(3000, Math.min(50000, Math.round(searchRadiusM)));
      this.setData({ lat, lng, searchRadiusM });

      const list = await request("/photographers/nearby", {
        params: {
          lat,
          lng,
          max_distance_m: searchRadiusM,
          limit: 100,
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
        const previewFixed = preview.map((u) => (u && u.startsWith("/") ? base + u : u)).filter(Boolean);
        const portfolioCount =
          typeof p.portfolio_count === "number" ? p.portfolio_count : previewFixed.length;
        const rateHourMin =
          typeof p.rate_hour_min_cents === "number" ? Math.round(p.rate_hour_min_cents / 100) : "";
        const rateItemMin =
          typeof p.rate_item_min_cents === "number" ? Math.round(p.rate_item_min_cents / 100) : "";
        const rateParts = [];
        if (rateHourMin) rateParts.push(`¥${rateHourMin}/小时起`);
        if (rateItemMin) rateParts.push(`¥${rateItemMin}/张起`);

        const distanceCopy = typeof p.distance_copy === "string" ? p.distance_copy : "";
        return {
          ...p,
          display_name: displayName,
          avatar_url: avatarUrl,
          distanceCopy,
          starting_price_yuan:
            typeof p.starting_price_cents === "number" ? Math.round(p.starting_price_cents / 100) : "",
          preview_image_urls: previewFixed,
          preview_count: previewFixed.length,
          preview_empty: previewFixed.length === 0,
          portfolio_count: portfolioCount,
          rate_hour_min_yuan: rateHourMin,
          rate_item_min_yuan: rateItemMin,
          rate_copy: rateParts.join(" · ")
        };
      });

      const markerOverflow = fixed.length > 80;
      const markerSource = markerOverflow ? fixed.slice(0, 80) : fixed;
      const markerSize = markerOverflow ? 28 : 36;
      const withMapAvatarStyle = (url) => {
        if (!url || typeof url !== "string") return "";
        if (!url.startsWith("http://") && !url.startsWith("https://")) return url;
        if (!url.includes("/media/")) {
          return `${base}/media/styled/avatar?style=map_avatar&v=2&url=${encodeURIComponent(url)}`;
        }
        const sep = url.includes("?") ? "&" : "?";
        return `${url}${sep}style=map_avatar&v=2`;
      };
      const markers = markerSource.map((p) => {
        const marker = {
          id: p.id,
          latitude: p.service_center_lat,
          longitude: p.service_center_lng,
          title: p.display_name || `#${p.id}`,
          width: markerSize,
          height: markerSize
        };
        if (p.avatar_url && (p.avatar_url.startsWith("http://") || p.avatar_url.startsWith("https://"))) {
          marker.iconPath = withMapAvatarStyle(p.avatar_url);
        } else if (!markerOverflow) {
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

      // 城市文案：MVP 先给“已定位”语义（无地理编码就不猜城市）
      const selectedId = this.data.selected?.id;
      const selected = fixed.find((item) => item.id === selectedId) || null;
      const circles = selected
        ? [
            {
              latitude: selected.service_center_lat,
              longitude: selected.service_center_lng,
              radius: selected.service_radius_m,
              color: "#11182715",
              fillColor: "#11182708",
              strokeWidth: 2
            }
          ]
        : [];
      this.setData({
        cityText: "已定位",
        list: fixed,
        markers,
        circles,
        selected,
        markerOverflow
      });
      this.reportExposureEvents(fixed);
    } catch (e) {
      const msg = e?.message || "加载失败";
      this.setData({ errorText: msg });
      wx.showToast({ title: msg.slice(0, 15), icon: "none" });
    } finally {
      this.setData({ loading: false });
    }
  },

  onRegionChange(e) {
    if (e.type !== "end") return;
    if (this._regionDebounceTimer) clearTimeout(this._regionDebounceTimer);
    this._regionDebounceTimer = setTimeout(() => {
      this.refreshByCurrentRegion();
    }, 300);
  },

  async refreshByCurrentRegion() {
    if (!this.mapCtx || this.data.loading) return;
    try {
      const region = await new Promise((resolve, reject) => {
        this.mapCtx.getRegion({
          success: resolve,
          fail: reject
        });
      });
      const ne = region?.northeast;
      const sw = region?.southwest;
      if (!ne || !sw) return;
      const centerLat = (ne.latitude + sw.latitude) / 2;
      const centerLng = (ne.longitude + sw.longitude) / 2;
      const distanceToCorner = this.haversineDistanceM(centerLat, centerLng, ne.latitude, ne.longitude);
      const maxDistanceM = Math.max(3000, Math.min(50000, Math.round(distanceToCorner)));
      await this.refresh({ lat: centerLat, lng: centerLng, maxDistanceM });
    } catch (_e) {
      // ignore map region refresh failure
    }
  },

  onMarkerTap(e) {
    const id = e.markerId;
    const p = (this.data.list || []).find((x) => x.id === id);
    if (!p) return;
    this.trackEvents([
      {
        event_type: "photographer_click",
        photographer_id: p.id,
        channel: "map_marker",
        lat: this.data.lat,
        lng: this.data.lng,
        extra: { source: "marker_tap" }
      }
    ]);
    const distance = encodeURIComponent(p.distanceCopy || "");
    wx.navigateTo({ url: `/pages/photographer/index?id=${id}&distance=${distance}` });
  },

  goDetail(e) {
    const id = e.currentTarget.dataset.id;
    if (id) {
      this.trackEvents([
        {
          event_type: "photographer_click",
          photographer_id: Number(id),
          channel: "map_list",
          lat: this.data.lat,
          lng: this.data.lng,
          extra: { source: "list_card" }
        }
      ]);
    }
    const p = (this.data.list || []).find((x) => Number(x.id) === Number(id));
    const distance = encodeURIComponent(p?.distanceCopy || "");
    wx.navigateTo({ url: `/pages/photographer/index?id=${id}&distance=${distance}` });
  },

  goDetailSelected() {
    const id = this.data.selected?.id;
    if (!id) return;
    const distance = encodeURIComponent(this.data.selected?.distanceCopy || "");
    wx.navigateTo({ url: `/pages/photographer/index?id=${id}&distance=${distance}` });
  },

  contactSelected() {
    const p = this.data.selected;
    if (!p) return;
    const options = [];
    if (p.wechat_id) options.push("复制微信号");
    if (p.phone) options.push("拨打电话");
    options.push("查看主页");
    wx.showActionSheet({
      itemList: options,
      success: (res) => {
        const action = options[res.tapIndex];
        if (action === "复制微信号") {
          wx.setClipboardData({
            data: p.wechat_id,
            success: () => wx.showToast({ title: "微信号已复制", icon: "none" })
          });
          this.trackEvents([
            {
              event_type: "photographer_contact",
              photographer_id: p.id,
              channel: "map_sheet",
              lat: this.data.lat,
              lng: this.data.lng,
              extra: { action: "copy_wechat" }
            }
          ]);
          return;
        }
        if (action === "拨打电话") {
          wx.makePhoneCall({ phoneNumber: p.phone });
          this.trackEvents([
            {
              event_type: "photographer_contact",
              photographer_id: p.id,
              channel: "map_sheet",
              lat: this.data.lat,
              lng: this.data.lng,
              extra: { action: "phone_call" }
            }
          ]);
          return;
        }
        this.goDetailSelected();
      }
    });
  },

  bookSelected() {
    const id = this.data.selected?.id;
    if (!id) return;
    const distance = encodeURIComponent(this.data.selected?.distanceCopy || "");
    wx.navigateTo({ url: `/pages/photographer/index?id=${id}&distance=${distance}` });
  },

  closeSelected() {
    this.setData({ selected: null, circles: [] });
  },

  reportExposureEvents(list) {
    if (!Array.isArray(list) || !list.length) return;
    const events = [];
    const exposureSet = this._exposureSet || new Set();
    this._exposureSet = exposureSet;
    list.slice(0, 30).forEach((p) => {
      if (!p?.id) return;
      const key = String(p.id);
      if (exposureSet.has(key)) return;
      exposureSet.add(key);
      events.push({
        event_type: "photographer_exposure",
        photographer_id: p.id,
        channel: "map_list",
        lat: this.data.lat,
        lng: this.data.lng
      });
    });
    this.trackEvents(events);
  },

  trackEvents(events) {
    trackBatch(events);
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
});

