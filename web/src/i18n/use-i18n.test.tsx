import { act, render, screen } from "@testing-library/react";
import { Suspense } from "react";
import { describe, expect, it, vi } from "vitest";
import { I18nProvider } from "./context";
import { ja } from "./messages/ja";
import { getI18n } from "./server";
import { createI18n } from "./translator";
import { useI18n } from "./use-i18n";
import { useI18n as useServerI18n } from "./use-i18n.server";

vi.mock("./server", () => ({ getI18n: vi.fn() }));

function Label({ hook }: { hook: typeof useI18n }) {
  const { t, locale } = hook();
  return (
    <p>
      {locale}: {t.nav.rankings}
    </p>
  );
}

describe("useI18n", () => {
  it("reads English without a provider", () => {
    render(<Label hook={useI18n} />);
    expect(screen.getByText("en: Rankings")).toBeInTheDocument();
  });

  it("reads the provider's language", () => {
    render(
      <I18nProvider locale="ja" messages={ja}>
        <Label hook={useI18n} />
      </I18nProvider>,
    );
    expect(screen.getByText(`ja: ${ja.nav.rankings}`)).toBeInTheDocument();
  });
});

describe("useI18n on the server", () => {
  it("reads the request's language", async () => {
    vi.mocked(getI18n).mockResolvedValue(createI18n("ja", ja));
    await act(() => {
      render(
        <Suspense fallback={null}>
          <Label hook={useServerI18n} />
        </Suspense>,
      );
      return Promise.resolve();
    });
    expect(screen.getByText(`ja: ${ja.nav.rankings}`)).toBeInTheDocument();
  });
});
