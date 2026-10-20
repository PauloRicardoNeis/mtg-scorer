"use client";
import { useI18n } from "#i18n";

export default function ErrorView({ reset }: { reset: () => void }) {
  const { t } = useI18n();
  return (
    <section className="state" role="alert">
      <h1>{t.error.title}</h1>
      <p>{t.error.body}</p>
      <button onClick={reset}>{t.common.retry}</button>
    </section>
  );
}
