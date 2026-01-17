import { defineConfig } from "eslint/config";
import nextConfig from "eslint-config-next";

export default defineConfig([
  {
    ignores: ["worker/", "agent/", ".next/", "node_modules/", ".venv/", "dist/"],
  },
  ...nextConfig,
  {
    files: ["**/*.ts", "**/*.tsx"],
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      "@typescript-eslint/no-deprecated": "warn",
    },
  },
]);
