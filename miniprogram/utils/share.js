const DEFAULT_HOME_PATH = "/pages/home/index";
const DEFAULT_TITLE = "Close Shot｜发现附近摄影师";
const DEFAULT_TIMELINE_TITLE = "Close Shot：这附近，谁拍得好？";

function enableShareMenu() {
  if (typeof wx === "undefined" || typeof wx.showShareMenu !== "function") return;
  wx.showShareMenu({
    withShareTicket: true,
    menus: ["shareAppMessage", "shareTimeline"]
  });
}

function buildPath(path, query = {}) {
  const qs = buildQuery(query);
  return qs ? `${path}?${qs}` : path;
}

function buildQuery(query = {}) {
  const pairs = Object.keys(query)
    .filter((key) => query[key] !== undefined && query[key] !== null && query[key] !== "")
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(String(query[key]))}`);
  return pairs.join("&");
}

function getHomeShareConfig(options = {}) {
  return {
    title: options.title || DEFAULT_TITLE,
    path: buildPath(DEFAULT_HOME_PATH, options.query || {}),
    imageUrl: options.imageUrl || undefined
  };
}

function getHomeTimelineConfig(options = {}) {
  return {
    title: options.title || DEFAULT_TIMELINE_TITLE,
    query: buildQuery(options.query || {}),
    imageUrl: options.imageUrl || undefined
  };
}

function getPhotographerShareConfig(photographer = {}, options = {}) {
  const id = photographer.id || options.id;
  const name = photographer.display_name || (id ? `摄影师 #${id}` : "摄影师");
  const cover = resolvePhotographerShareImage(photographer);
  return {
    title: `推荐 ${name} 的摄影主页`,
    path: buildPath("/pages/photographer/index", { id, from: options.from || "share" }),
    imageUrl: cover || undefined
  };
}

function getPhotographerTimelineConfig(photographer = {}, options = {}) {
  const id = photographer.id || options.id;
  const name = photographer.display_name || (id ? `摄影师 #${id}` : "摄影师");
  const cover = resolvePhotographerShareImage(photographer);
  return {
    title: `${name} 的摄影主页`,
    query: buildQuery({ id, from: "timeline" }),
    imageUrl: cover || undefined
  };
}

function resolvePhotographerShareImage(photographer = {}) {
  if (photographer.avatar_url) return photographer.avatar_url;
  if (Array.isArray(photographer.portfolio_items) && photographer.portfolio_items[0]?.image_url) {
    return photographer.portfolio_items[0].image_url;
  }
  if (Array.isArray(photographer.preview_image_urls) && photographer.preview_image_urls[0]) {
    return photographer.preview_image_urls[0];
  }
  return "";
}

module.exports = {
  enableShareMenu,
  getHomeShareConfig,
  getHomeTimelineConfig,
  getPhotographerShareConfig,
  getPhotographerTimelineConfig
};
