import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const appDir = path.dirname(fileURLToPath(import.meta.url));
/** Monorepo root (parent of `uis/`) so `lib/assets.ts` can import `assets/backgrounds/*`. */
const monorepoRoot = path.resolve(appDir, "../..");

/**
 * Server-side FastAPI origin for the Next.js rewrite proxy.
 * Docker Compose sets this to http://backend:8000 (Compose service name).
 */
const apiProxyTarget = process.env.API_PROXY_TARGET?.replace(/\/$/, "");

const nextConfig: NextConfig = {
  webpack: (config, { dev }) => {
    // Docker Desktop bind mounts often miss inotify; polling makes dev HMR reliable.
    if (dev) {
      config.watchOptions = {
        poll: 1000,
        aggregateTimeout: 300,
      };
    }
    return config;
  },
  experimental: {
    externalDir: true,
  },
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  turbopack: {
    root: monorepoRoot,
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
