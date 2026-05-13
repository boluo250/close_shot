import { defineStore } from "pinia";
import type { AuthIdentity } from "../lib/authIdentity";

type AuthState = {
  token: string | null;
  identity: AuthIdentity | null;
};

export const useAuthStore = defineStore("auth", {
  state: (): AuthState => ({
    token: localStorage.getItem("token"),
    identity: (() => {
      const raw = localStorage.getItem("auth_identity");
      if (!raw) return null;
      try {
        return JSON.parse(raw) as AuthIdentity;
      } catch {
        return null;
      }
    })()
  }),
  actions: {
    setToken(token: string) {
      this.token = token;
      localStorage.setItem("token", token);
    },
    setIdentity(identity: AuthIdentity | null) {
      this.identity = identity;
      if (identity) {
        localStorage.setItem("auth_identity", JSON.stringify(identity));
      } else {
        localStorage.removeItem("auth_identity");
      }
    },
    logout() {
      this.token = null;
      localStorage.removeItem("token");
      this.setIdentity(null);
    }
  }
});
