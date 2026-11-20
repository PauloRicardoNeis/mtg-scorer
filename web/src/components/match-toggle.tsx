import { useI18n } from "#i18n";

/**
 * How several selected colors or types combine: off, a card has any of them;
 * on, every one. Off sends nothing, so the address keeps the API's default.
 */
export function MatchToggle({
  name,
  label,
  all,
  form,
}: {
  name: string;
  /** What "on" means, as the checkbox's name. */
  label: string;
  all: boolean;
  form?: string | undefined;
}) {
  const { t } = useI18n();
  return (
    <label className="match-toggle" title={label}>
      <input
        type="checkbox"
        name={name}
        value="all"
        form={form}
        defaultChecked={all}
      />
      <span className="match-any" aria-hidden="true">
        {t.common.matchAny}
      </span>
      <span className="match-all" aria-hidden="true">
        {t.common.matchAll}
      </span>
      <span className="sr-only">{label}</span>
    </label>
  );
}
