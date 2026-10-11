import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = path.dirname(fileURLToPath(import.meta.url));
const uisRoot = path.resolve(appRoot, "..");

const nextConfig: NextConfig = {
  // Root at uis/ so ../incidents compiles with this app, without walking up
  // to the repository-root lockfile (Windows MAX_PATH).
  turbopack: {
    root: uisRoot,
  },
};

export default nextConfig;
