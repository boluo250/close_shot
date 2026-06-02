const { getToken } = require("./auth");
const { request } = require("./request");

let subscribeConfigCache = null;
let subscribeConfigLoading = null;
const PHOTOGRAPHER_NOTIFY_STATUS_KEY = "photographer_notify_status_v1";

function uniqueTemplateIds(values) {
  return Array.from(new Set((values || []).filter((item) => typeof item === "string" && item.trim())));
}

function tokenFingerprint(token) {
  if (!token) return "";
  return token.slice(-24);
}

async function loadAppointmentSubscribeConfig(options = {}) {
  const { refresh = false } = options;
  if (subscribeConfigCache && !refresh) return subscribeConfigCache;
  if (subscribeConfigLoading && !refresh) return subscribeConfigLoading;
  if (!getToken()) return null;
  subscribeConfigLoading = request("/appointments/subscribe-config", { auth: true })
    .then((data) => {
      subscribeConfigCache = data || {};
      return subscribeConfigCache;
    })
    .catch((_e) => null)
    .finally(() => {
      subscribeConfigLoading = null;
    });
  return subscribeConfigLoading;
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

async function warmAppointmentSubscribeConfig() {
  return loadAppointmentSubscribeConfig();
}

async function requestPhotographerAppointmentSubscriptions() {
  const config = await loadAppointmentSubscribeConfig();
  return requestTemplates([config?.photographer_new_appointment_template_id]);
}

async function requestCustomerAppointmentAcceptedSubscription() {
  const config = await loadAppointmentSubscribeConfig();
  return requestTemplates([config?.customer_appointment_accepted_template_id]);
}

async function requestCustomerAppointmentCompletedSubscription() {
  const config = await loadAppointmentSubscribeConfig();
  return requestTemplates([config?.customer_appointment_completed_template_id]);
}

function summarizeAppointmentSubscribeResult(result) {
  if (!result || result.skipped) return "skipped";
  const states = Object.keys(result)
    .filter((key) => key !== "errMsg" && typeof result[key] === "string")
    .map((key) => result[key]);
  if (!states.length) return "unknown";
  if (states.includes("accept")) return "accept";
  if (states.some((item) => item === "reject" || item === "ban" || item === "filter")) return "reject";
  return "unknown";
}

function isPhotographerNotificationEnabled() {
  const token = getToken();
  const fingerprint = tokenFingerprint(token);
  if (!fingerprint) return false;
  try {
    const cache = wx.getStorageSync(PHOTOGRAPHER_NOTIFY_STATUS_KEY);
    return !!(cache && typeof cache === "object" && cache[fingerprint]);
  } catch (_e) {
    return false;
  }
}

function setPhotographerNotificationEnabled(enabled) {
  const token = getToken();
  const fingerprint = tokenFingerprint(token);
  if (!fingerprint) return;
  try {
    const cache = wx.getStorageSync(PHOTOGRAPHER_NOTIFY_STATUS_KEY);
    const next = cache && typeof cache === "object" ? { ...cache } : {};
    next[fingerprint] = !!enabled;
    wx.setStorageSync(PHOTOGRAPHER_NOTIFY_STATUS_KEY, next);
  } catch (_e) {
    // ignore storage failures
  }
}

function clearAppointmentSubscribeCache() {
  subscribeConfigCache = null;
  subscribeConfigLoading = null;
}

module.exports = {
  loadAppointmentSubscribeConfig,
  requestTemplates,
  warmAppointmentSubscribeConfig,
  requestPhotographerAppointmentSubscriptions,
  requestCustomerAppointmentAcceptedSubscription,
  requestCustomerAppointmentCompletedSubscription,
  summarizeAppointmentSubscribeResult,
  isPhotographerNotificationEnabled,
  setPhotographerNotificationEnabled,
  clearAppointmentSubscribeCache
};
