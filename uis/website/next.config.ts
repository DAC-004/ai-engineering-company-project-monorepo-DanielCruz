import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = path.dirname(fileURLToPath(import.meta.url));

/**
 * Server-side FastAPI origin for the Next.js rewrite proxy.
 * Browser code must never see this value: it is not a NEXT_PUBLIC_ variable.
 * Docker Compose sets this to http://backend:8000 (Compose service name).
 * Local non-Docker development sets it to http://127.0.0.1:8000.
 */
const apiProxyTarget = process.env.API_PROXY_TARGET?.replace(/\/$/, "");

const nextConfig: NextConfig = {
  // Host browsers reach the container via 127.0.0.1/localhost while next
  // listens on 0.0.0.0. Without this, Next.js 16 blocks /_next assets and
  // client components never hydrate.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  turbopack: {
    root: appRoot,
  },
  async rewrites() {
    if (!apiProxyTarget) {
      return [];
    }
    return [
      {
        source: "/backend/:path*",
        destination: `${apiProxyTarget}/:path*`,
      },
    ];
  },
};

export default nextConfig;
