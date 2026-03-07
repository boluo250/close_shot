function normalizePrefix(v: string): string {
  const trimmed = (v || "").trim();
  if (!trimmed) return "";
  const withLeading = trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  return withLeading.replace(/\/+$/, "");
}

export const ADMIN_SECURITY_SUFFIX = "x8r7m2q4p9";
export const ADMIN_WEB_BASE = normalizePrefix(import.meta.env.VITE_ADMIN_WEB_BASE || `/ops-${ADMIN_SECURITY_SUFFIX}`);
export const ADMIN_API_PREFIX = normalizePrefix(
  import.meta.env.VITE_ADMIN_API_PREFIX || `/admin-${ADMIN_SECURITY_SUFFIX}`
);
export const ADMIN_LOGIN_PATH = `${ADMIN_WEB_BASE}/login`;
export const ADMIN_HOME_PATH = `${ADMIN_WEB_BASE}/studio/upload`;

export function withAdminWebBase(subPath: string): string {
  const s = subPath.startsWith("/") ? subPath : `/${subPath}`;
  return `${ADMIN_WEB_BASE}${s}`;
}

export function withAdminApiPrefix(subPath: string): string {
  const s = subPath.startsWith("/") ? subPath : `/${subPath}`;
  return `${ADMIN_API_PREFIX}${s}`;
}

