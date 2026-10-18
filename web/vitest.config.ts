import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Unit tests sit beside the code under src (not src/app, whose server pages the
// Playwright suite in tests/ exercises).
export default defineConfig({
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/test/setup.ts"],
    mockReset: true,
    restoreMocks: true,
    unstubEnvs: true,
    unstubGlobals: true,
    coverage: {
      provider: "v8",
      include: ["src/lib/**/*.{ts,tsx}", "src/components/**/*.{ts,tsx}"],
      exclude: ["src/lib/api.generated.ts", "src/**/*.test.{ts,tsx}"],
      reporter: ["text", "html", "lcov", "cobertura"],
      reportsDirectory: "./coverage",
      // The achieved coverage, rounded down; raise these as coverage grows.
      thresholds: {
        statements: 100,
        branches: 99,
        functions: 100,
        lines: 100,
      },
    },
  },
});
