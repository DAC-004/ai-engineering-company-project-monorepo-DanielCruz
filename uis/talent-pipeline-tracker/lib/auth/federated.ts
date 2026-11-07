import { apiFetch } from "@/lib/auth/api";
import type { TokenResponse } from "@/lib/auth/types";

export const MICROSOFT_CALLBACK_PATH = "/auth/callback/microsoft";
export const MICROSOFT_REDIRECT_URI =
  typeof window === "undefined"
    ? "http://localhost:3000/auth/callback/microsoft"
    : `${window.location.origin}${MICROSOFT_CALLBACK_PATH}`;

const TX_BINDING_STORAGE_KEY = "hc_federated_tx_binding";

export type FederatedPurpose = "link" | "login";

export type FederatedStartResponse = {
  authorization_url: string;
  state: string;
  tx_binding: string;
};

export type FederatedLinkPublic = {
  provider: string;
  provider_user_id: string;
  email_at_link_time: string | null;
  linked_at: string | null;
  provisioned_by_it: boolean;
};

export type FederatedStatusResponse = {
  provider: string;
  linked: boolean;
  link: FederatedLinkPublic | null;
  has_password: boolean;
  can_unlink: boolean;
  unlink_blocked_reason: string | null;
};

export const rememberFederatedTxBinding = (txBinding: string): void => {
  window.sessionStorage.setItem(TX_BINDING_STORAGE_KEY, txBinding);
};

export const takeFederatedTxBinding = (): string => {
  const value = window.sessionStorage.getItem(TX_BINDING_STORAGE_KEY) ?? "";
  window.sessionStorage.removeItem(TX_BINDING_STORAGE_KEY);
  return value;
};

export const startMicrosoftFederated = async (
  purpose: FederatedPurpose,
  options: { auth: boolean; redirectUri?: string },
): Promise<FederatedStartResponse> => {
  const started = await apiFetch<FederatedStartResponse>(
    "/auth/federated/microsoft/start",
    {
      method: "POST",
      auth: options.auth,
      body: JSON.stringify({
        purpose,
        redirect_uri: options.redirectUri ?? MICROSOFT_REDIRECT_URI,
      }),
    },
  );
  rememberFederatedTxBinding(started.tx_binding);
  return started;
};

export const completeMicrosoftFederated = (
  payload: { code: string; state: string; redirectUri?: string },
  options: { auth: boolean },
): Promise<TokenResponse | FederatedStatusResponse> =>
  apiFetch<TokenResponse | FederatedStatusResponse>(
    "/auth/federated/microsoft/callback",
    {
      method: "POST",
      auth: options.auth,
      body: JSON.stringify({
        code: payload.code,
        state: payload.state,
        redirect_uri: payload.redirectUri ?? MICROSOFT_REDIRECT_URI,
        tx_binding: takeFederatedTxBinding(),
      }),
    },
  );

export const fetchMicrosoftLinkStatus = (): Promise<FederatedStatusResponse> =>
  apiFetch<FederatedStatusResponse>("/auth/federated/microsoft/status", {
    auth: true,
    method: "GET",
  });

export const unlinkMicrosoft = (): Promise<FederatedStatusResponse> =>
  apiFetch<FederatedStatusResponse>("/auth/federated/microsoft", {
    auth: true,
    method: "DELETE",
  });

export const isTokenResponse = (
  value: TokenResponse | FederatedStatusResponse,
): value is TokenResponse => "access_token" in value;
