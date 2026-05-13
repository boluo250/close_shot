import { api } from "./api";
import { ADMIN_HOME_PATH, STUDIO_HOME_PATH } from "./adminSecurity";

export type AuthIdentity = {
  role: string;
  photographer_status: string | null;
  photographer_reject_reason: string | null;
  certification_level: number;
  is_member: boolean;
  member_expires_at: string | null;
};

export async function fetchMyIdentity(): Promise<AuthIdentity> {
  const { data } = await api.get<AuthIdentity>("/me/identity");
  return data;
}

export function resolveHomePath(identity: AuthIdentity | null | undefined): string {
  return identity?.role === "admin" ? ADMIN_HOME_PATH : STUDIO_HOME_PATH;
}
