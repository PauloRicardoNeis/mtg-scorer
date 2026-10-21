// @ts-check
// Type-checked linting for the web application: typescript-eslint over the project's
// tsconfig, the React hooks and Next.js rules, accessible JSX, and the test-runner rules
// for vitest and Playwright files. `npm run lint` runs it; demo.py runs it in the build
// stage before the unit tests.
import js from "@eslint/js";
import next from "@next/eslint-plugin-next";
import vitest from "@vitest/eslint-plugin";
import jsxA11y from "eslint-plugin-jsx-a11y";
import playwright from "eslint-plugin-playwright";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "node_modules/",
      ".next/",
      "coverage/",
      "playwright-report/",
      "test-results/",
      "reports/",
      ".stryker-tmp/",
      "src/lib/api.generated.ts",
      "next-env.d.ts",
      "eslint.config.mjs",
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  reactHooks.configs.flat.recommended,
  jsxA11y.flatConfigs.recommended,
  next.configs.recommended,
  {
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
      globals: { ...globals.browser, ...globals.node },
    },
    rules: {
      // Names that start with an underscore are declared unused on purpose.
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          destructuredArrayIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
      // Card scans and mana symbols come from Scryfall's CDN at the size the markup
      // states; next/image would proxy a third party for no gain.
      "@next/next/no-img-element": "off",
    },
  },
  {
    // Pages are async Server Components: they await their data and render inside the
    // same try/catch. The React Compiler rule reads that as catching render errors,
    // which only applies to client components.
    files: ["src/app/**/*.tsx"],
    rules: { "react-hooks/error-boundaries": "off" },
  },
  {
    files: ["src/**/*.test.{ts,tsx}"],
    ...vitest.configs.recommended,
    rules: {
      ...vitest.configs.recommended.rules,
      // vitest accepts a message as the second argument of expect.
      "vitest/valid-expect": ["error", { maxArgs: 2 }],
      // Tests render plain anchors to check the primitives, not to navigate.
      "@next/next/no-html-link-for-pages": "off",
    },
  },
  { files: ["tests/**/*.ts"], ...playwright.configs["flat/recommended"] },
);
