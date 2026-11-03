"use client";

import { Suspense } from "react";

import { LoginForm } from "@/components/auth/LoginForm";
import { LoginResetNotice } from "@/components/auth/LoginResetNotice";

/**
 * Single client boundary for the login card so static copy and form hydrate together.
 */
export const LoginScreen = () => {
  return (
    <div className="auth-screen">
      <div className="auth-card">
        <p className="eyebrow">HealthCore Digital</p>
        <h1>Sign in</h1>
        <p className="auth-lede">
          Authenticate against the HealthCore API. Your JWT is stored in localStorage
          for protected requests.
        </p>
        <Suspense fallback={null}>
          <LoginResetNotice />
        </Suspense>
        <LoginForm />
      </div>
    </div>
  );
};
