import { AUTH_TOKEN_STORAGE_KEY } from "@/lib/auth/constants";

/**
 * JWT session helpers.
 *
 * The AUTH-02 contract requires the access token to live in localStorage.
 * These helpers are browser-only; callers must guard against SSR.
 */

export const getAccessToken = (): string | null => {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);
};

export const setAccessToken = (token: string): void => {
  window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
};

export const clearAccessToken = (): void => {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
};

export const hasAccessToken = (): boolean => Boolean(getAccessToken());
