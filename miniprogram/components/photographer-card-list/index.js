Component({
  properties: {
    list: {
      type: Array,
      value: []
    },
    loading: {
      type: Boolean,
      value: false
    },
    errorText: {
      type: String,
      value: ""
    },
    emptyTitle: {
      type: String,
      value: "还没有内容"
    },
    emptyDesc: {
      type: String,
      value: ""
    },
    source: {
      type: String,
      value: "nearby"
    }
  },
  methods: {
    goDetail(e) {
      const id = e.currentTarget.dataset.id;
      const distance = encodeURIComponent(e.currentTarget.dataset.distance || "");
      const source = encodeURIComponent(this.data.source || "nearby");
      wx.navigateTo({ url: `/pages/photographer/index?id=${id}&distance=${distance}&from=${source}` });
    }
  }
});
