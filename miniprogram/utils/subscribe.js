const { getToken } = require("./auth");
const { request } = require("./request");

let subscribeConfigCache = null;

function uniqueTemplateIds(values) {
  return Array.from(new Set((values || []).filter((item) => typeof item === "string" && item.trim())));
}

async function loadAppointmentSubscribeConfig() {
  if (subscribeConfigCache) return subscribeConfigCache;
  if (!getToken()) return null;
  try {
    const data = await request("/appointments/subscribe-config", { auth: true });
    subscribeConfigCache = data || {};
    return subscribeConfigCache;
  } catch (_e) {
    return null;
  }
}

async function requestTemplates(templateIds) {
  const tmplIds = uniqueTemplateIds(templateIds);
  if (!tmplIds.length || typeof wx.requestSubscribeMessage !== "function") {
    return { skipped: true };
  }
  return new Promise((resolve) => {
    wx.requestSubscribeMessage({
      tmplIds,
      complete: (res) => resolve(res || {})
    });
  });
}

async function requestPhotographerAppointmentSubscriptions() {
  const config = await loadAppointmentSubscribeConfig();
  return requestTemplates([config?.photographer_new_appointment_template_id]);
}

async function requestCustomerAppointmentSubscriptions(options = {}) {
  const { includeAccepted = true, includeCompleted = true } = options;
  const config = await loadAppointmentSubscribeConfig();
  const ids = [];
  if (includeAccepted) ids.push(config?.customer_appointment_accepted_template_id);
  if (includeCompleted) ids.push(config?.customer_appointment_completed_template_id);
  return requestTemplates(ids);
}

function clearAppointmentSubscribeCache() {
  subscribeConfigCache = null;
}

module.exports = {
  requestPhotographerAppointmentSubscriptions,
  requestCustomerAppointmentSubscriptions,
  clearAppointmentSubscribeCache
};
