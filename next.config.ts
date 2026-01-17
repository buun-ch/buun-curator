import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Transpile packages that need to be bundled by Next.js
  transpilePackages: ["@yaireo/tagify"],
  // Externalize packages that have issues with Next.js bundling:
  // - @copilotkit/runtime: See https://github.com/CopilotKit/CopilotKit/issues/2802
  // - pino: thread-stream test files require 'tap' dev dependency
  serverExternalPackages: ["@copilotkit/runtime", "pino", "jose"],
  // Include dependencies of serverExternalPackages in standalone output
  outputFileTracingIncludes: {
    "/**/*": ["./node_modules/jose/**/*"],
  },
  allowedDevOrigins: process.env.ALLOWED_DEV_ORIGINS?.split(","),
  // Disable health check request logs when DISABLE_HEALTH_REQUEST_LOGS=1
  logging: process.env.DISABLE_HEALTH_REQUEST_LOGS === '1' ? {
    incomingRequests: {
      ignore: [/healthz/],
    },
  } : undefined,
  devIndicators: {
    position: "bottom-right",
  },
};

export default nextConfig;
