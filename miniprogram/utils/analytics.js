const { request } = require("./request");

function trackBatch(events) {
  const payload = (events || [])
    .filter((item) => item && item.event_type)
    .slice(0, 100)
    .map((item) => ({
      event_type: String(item.event_type),
      photographer_id: item.photographer_id || null,
      channel: item.channel || "mini_program",
      lat: typeof item.lat === "number" ? item.lat : null,
      lng: typeof item.lng === "number" ? item.lng : null,
      extra: item.extra && typeof item.extra === "object" ? item.extra : {}
    }));

  if (!payload.length) return;
  request("/analytics/events/batch", {
    method: "POST",
    data: { events: payload }
  }).catch(() => {});
}

module.exports = {
  trackBatch
};
