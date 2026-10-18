import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // /api/* is forwarded to the FastAPI service by src/app/api/[...path]/route.ts, which reads API_URL at runtime.
  output: "standalone",
};

export default nextConfig;
