/**
 * Daniel E11: public registration screen and entry links are disabled.
 * Source-text inspection, not a rendered browser journey.
 *
 * C1 login entrypoint mounts LoginForm. C2 mounts LoginScreen, which mounts
 * LoginForm and LoginResetNotice. This file follows the active entrypoint
 * instead of assuming LoginScreen.tsx is present.
 */

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const trackerRoot = join(__dirname, "..", "..");

const toPosix = (value: string) => value.replaceAll("\\", "/");

const readRequired = (...segments: string[]): string => {
  const relative = toPosix(join(...segments));
  const absolute = join(trackerRoot, ...segments);
  if (!existsSync(absolute)) {
    throw new Error(`Required mounted source is missing: ${relative}`);
  }
  return readFileSync(absolute, "utf8");
};

const LOCAL_COMPONENT_IMPORT =
  /import\s+(?:\{([^}]+)\}|(\w+))\s+from\s+"@\/components\/([^"]+)"/g;

const importedExportNames = (clause: string): string[] =>
  clause
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0 && !part.startsWith("type "))
    .map((part) => {
      const renamed = part.match(/^(\w+)\s+as\s+(\w+)$/);
      return renamed ? renamed[2] : part;
    });

const collectMountedLocalSources = (entrypointSource: string): string[] => {
  const sources = [entrypointSource];
  const pending = [entrypointSource];
  const seen = new Set<string>();

  while (pending.length > 0) {
    const current = pending.shift();
    if (current === undefined) {
      break;
    }
    const importPattern = new RegExp(LOCAL_COMPONENT_IMPORT.source, "g");
    for (const match of current.matchAll(importPattern)) {
      const names = importedExportNames(match[1] ?? match[2] ?? "");
      const usedInJsx = names.some((name) => new RegExp(`<${name}\\b`).test(current));
      if (!usedInJsx) {
        continue;
      }
      const importedPath = match[3];
      if (seen.has(importedPath)) {
        continue;
      }
      seen.add(importedPath);
      const segments = ["components", ...importedPath.split("/").filter(Boolean)];
      segments[segments.length - 1] = `${segments[segments.length - 1]}.tsx`;
      const mounted = readRequired(...segments);
      sources.push(mounted);
      pending.push(mounted);
    }
  }
  return sources;
};

const activeLoginSurface = (): string => {
  const loginPage = readRequired("app", "login", "page.tsx");
  const mountsLoginForm = /<LoginForm\b/.test(loginPage);
  const mountsLoginScreen = /<LoginScreen\b/.test(loginPage);
  if (!mountsLoginForm && !mountsLoginScreen) {
    throw new Error(
      "Unrecognized login entrypoint: app/login/page.tsx must mount LoginForm or LoginScreen",
    );
  }
  return collectMountedLocalSources(loginPage).join("\n");
};

describe("public registration entry links", () => {
  const loginSurface = activeLoginSurface();
  const forgotForm = readRequired("components", "auth", "ForgotPasswordForm.tsx");

  it("does not offer a Register link from login", () => {
    expect(loginSurface).not.toContain('href="/register"');
    expect(loginSurface).not.toContain(">Register<");
  });

  it("keeps login password-recovery navigation", () => {
    expect(loginSurface).toContain('href="/forgot-password"');
    expect(loginSurface).toContain("Forgot your password?");
  });

  it("keeps forgot-password sign-in navigation", () => {
    expect(forgotForm).toContain('href="/login"');
    expect(forgotForm).not.toContain('href="/register"');
  });
});

describe("direct /register route", () => {
  const registerPage = readRequired("app", "register", "page.tsx");

  it("does not mount the signup form or account-creation submit", () => {
    expect(registerPage).not.toContain("RegisterForm");
    expect(registerPage).not.toContain("registerAndAuthenticate");
    expect(registerPage).not.toContain("Create account");
    expect(registerPage).not.toContain("auth-form");
    expect(registerPage).not.toContain('type="submit"');
  });

  it("directs visitors to login and password recovery", () => {
    expect(registerPage).toContain('href="/login"');
    expect(registerPage).toContain('href="/forgot-password"');
  });
});
