import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "node",
    globals: true,
    include: ["tests/**/*.test.ts"],
    exclude: ["**/node_modules/**", "tests/e2e/**"],
    pool: "forks",
    fileParallelism: false, // Run test files sequentially to avoid DB conflicts
    sequence: {
      concurrent: false, // Run tests within a file sequentially
    },
  },
  envPrefix: ["DATABASE_", "OPENAI_", "TEST_"],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./"),
    },
  },
});
