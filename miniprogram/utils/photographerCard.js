function normalizePhotographerCard(p, apiBaseUrl) {
  const displayName = p.display_name || `摄影师 #${p.id}`;
  const avatarUrl = p.avatar_url && p.avatar_url.startsWith("/") ? apiBaseUrl + p.avatar_url : p.avatar_url || "";

  const preview = Array.isArray(p.preview_image_urls) ? p.preview_image_urls : [];
  const previewFixed = preview.map((u) => (u && u.startsWith("/") ? apiBaseUrl + u : u)).filter(Boolean);

  const portfolioCount = typeof p.portfolio_count === "number" ? p.portfolio_count : previewFixed.length;
  const rateHourMin = typeof p.rate_hour_min_cents === "number" ? Math.round(p.rate_hour_min_cents / 100) : "";
  const rateItemMin = typeof p.rate_item_min_cents === "number" ? Math.round(p.rate_item_min_cents / 100) : "";
  const rateParts = [];
  if (rateHourMin) rateParts.push(`¥${rateHourMin}/小时起`);
  if (rateItemMin) rateParts.push(`¥${rateItemMin}/张起`);

  return {
    ...p,
    display_name: displayName,
    avatar_url: avatarUrl,
    distanceCopy: typeof p.distance_copy === "string" ? p.distance_copy : "",
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
}

module.exports = {
  normalizePhotographerCard
};
