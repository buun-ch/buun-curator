import { defineConfig } from "eslint/config";
import nextConfig from "eslint-config-next";
import simpleImportSort from "eslint-plugin-simple-import-sort";
import unusedImports from "eslint-plugin-unused-imports";

export default defineConfig([
  {
    ignores: [
      "worker/",
      "agent/",
      ".next/",
      ".claude/",
      "node_modules/",
      ".venv/",
      "dist/",
      "playwright-report/",
      "test-results/",
    ],
  },
  ...nextConfig,
  {
    files: ["**/*.ts", "**/*.tsx"],
    plugins: {
      "simple-import-sort": simpleImportSort,
      "unused-imports": unusedImports,
    },
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      "@typescript-eslint/no-deprecated": "warn",
      "@typescript-eslint/no-unused-vars": "off",
      "simple-import-sort/imports": "error",
      "simple-import-sort/exports": "error",
      "unused-imports/no-unused-imports": "error",
      "unused-imports/no-unused-vars": [
        "warn",
        {
          vars: "all",
          varsIgnorePattern: "^_",
          args: "after-used",
          argsIgnorePattern: "^_",
        },
      ],
    },
  },
]);
