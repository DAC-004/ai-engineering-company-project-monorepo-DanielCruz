"use client";

import { createContext, useContext, type ReactNode } from "react";

import type { AuthMeResponse } from "@/lib/auth/types";

const CurrentUserContext = createContext<AuthMeResponse | null>(null);

export const CurrentUserProvider = ({
  user,
  children,
}: {
  user: AuthMeResponse;
  children: ReactNode;
}) => <CurrentUserContext.Provider value={user}>{children}</CurrentUserContext.Provider>;

export const useCurrentUser = (): AuthMeResponse | null => useContext(CurrentUserContext);
