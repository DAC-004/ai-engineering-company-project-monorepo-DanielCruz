import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  // Keep Turbopack rooted on this app so monorepo parent lockfiles do not
  // inflate Windows build paths past MAX_PATH.
  turbopack: {
    root: appRoot,
  },
};

export default nextConfig;
