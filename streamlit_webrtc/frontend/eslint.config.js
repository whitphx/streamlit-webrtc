import globals from "globals";
import { defineConfig } from "eslint/config";
import pluginJs from "@eslint/js";
import tseslint from "typescript-eslint";
import pluginReact from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import pluginReactJSXRuntime from "eslint-plugin-react/configs/jsx-runtime.js";

/** @type {import('eslint').Linter.Config[]} */
export default defineConfig([
  { ignores: ["dist"] },
  { files: ["**/*.{js,mjs,cjs,ts,jsx,tsx}"] },
  { languageOptions: { globals: globals.browser } },
  pluginJs.configs.recommended,
  ...tseslint.configs.recommended,
  { settings: { react: { version: "detect" } } },
  pluginReact.configs.flat.recommended,
  reactHooks.configs["recommended-latest"],
  reactRefresh.configs.recommended,
  pluginReactJSXRuntime,
]);
