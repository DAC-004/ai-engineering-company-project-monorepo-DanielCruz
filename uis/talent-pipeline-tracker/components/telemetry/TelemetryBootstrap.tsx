"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import { toRoutePath, sanitizeTelemetryMessage } from "@/lib/telemetry/mapping";
import { track, startTelemetry } from "@/src/services/telemetry";

const PAGE_VIEW_DEBOUNCE_MS = 2_000;
const ERROR_THROTTLE_MS = 60_000;

const lastPageView: { route: string; at: number } = { route: "", at: 0 };
const errorThrottle = new Map<string, number>();
// Same-document Strict Mode remounts reuse this module and timeOrigin.
// A genuine reload creates a new document, re-executes the module, and
// gets a new timeOrigin, so a later full load stays eligible.
let fullLoadEmittedForTimeOrigin: number | null = null;

const currentRoute = (): string =>
  typeof window === "undefined" ? "/" : toRoutePath(window.location.pathname);

const sha256Hex = async (value: string): Promise<string> => {
  const digest = await window.crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(value),
  );
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
};

const trackPageViewed = (route: string, referrerRoute?: string): void => {
  const now = Date.now();
  if (
    lastPageView.route === route &&
    now - lastPageView.at < PAGE_VIEW_DEBOUNCE_MS
  ) {
    return;
  }
  lastPageView.route = route;
  lastPageView.at = now;
  const properties: Record<string, unknown> = { route };
  if (referrerRoute) {
    properties.referrer_route = referrerRoute;
  }
  track("page_viewed", properties);
};

const trackUncaughtError = async (
  errorName: string,
  message: string,
  stackOrReason: string,
): Promise<void> => {
  const route = currentRoute();
  const stackHash = await sha256Hex(stackOrReason || message);
  const fingerprint = `${errorName}:${stackHash}:${route}`;
  const last = errorThrottle.get(fingerprint) ?? 0;
  const now = Date.now();
  if (now - last < ERROR_THROTTLE_MS) {
    return;
  }
  errorThrottle.set(fingerprint, now);
  track("frontend_error_uncaught", {
    error_name: errorName || "Error",
    sanitized_message: sanitizeTelemetryMessage(message),
    route,
    stack_hash: stackHash,
  });
};

/**
 * One Navigation Timing full-load event per document. Strict Mode remounts
 * share timeOrigin; a real reload does not.
 */
const trackFullLoadCompleted = (): void => {
  const timeOrigin = performance.timeOrigin;
  if (fullLoadEmittedForTimeOrigin === timeOrigin) {
    return;
  }
  const navigation = performance.getEntriesByType(
    "navigation",
  )[0] as PerformanceNavigationTiming | undefined;
  const durationMs = navigation
    ? Math.max(0, Math.round(navigation.loadEventEnd))
    : Math.max(0, Math.round(performance.now()));
  fullLoadEmittedForTimeOrigin = timeOrigin;
  track("page_load_completed", {
    route: currentRoute(),
    duration_ms: durationMs,
    navigation_type: "full_load",
  });
};

/**
 * Starts the capture service and the technical baseline: page views, page
 * load timing, and uncaught frontend errors. Must render once at the app root.
 */
export const TelemetryBootstrap = () => {
  const pathname = usePathname();
  const previousRouteRef = useRef<string | null>(null);

  useEffect(() => {
    startTelemetry();

    const onError = (event: ErrorEvent) => {
      void trackUncaughtError(
        event.error instanceof Error ? event.error.name : "Error",
        event.message || "uncaught error",
        event.error instanceof Error
          ? (event.error.stack ?? event.message)
          : event.message,
      );
    };
    const onRejection = (event: PromiseRejectionEvent) => {
      const reason = event.reason;
      const message =
        reason instanceof Error
          ? reason.message
          : typeof reason === "string"
            ? reason
            : "unhandled rejection";
      void trackUncaughtError(
        reason instanceof Error ? reason.name : "UnhandledRejection",
        message,
        reason instanceof Error ? (reason.stack ?? message) : String(reason),
      );
    };

    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onRejection);
    trackFullLoadCompleted();

    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onRejection);
    };
  }, []);

  useEffect(() => {
    const route = toRoutePath(pathname || "/");
    const referrer = previousRouteRef.current;
    trackPageViewed(route, referrer ?? undefined);
    previousRouteRef.current = route;
  }, [pathname]);

  return null;
};
