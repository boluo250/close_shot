Component({
  properties: {
    value: { type: String, value: "classic" },
    size: { type: String, value: "sm" }
  },
  methods: {
    onPick(e) {
      const v = e.currentTarget.dataset.value;
      if (!v || v === this.data.value) return;
      this.triggerEvent("change", { value: v });
    }
  }
});

