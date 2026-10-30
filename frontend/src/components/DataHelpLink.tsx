import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { InfoIcon } from "../lib/icons";

export default function DataHelpLink({ anchor, children }: { anchor: string; children: React.ReactNode }) {
  const { t } = useTranslation();
  return (
    <Link
      to={`/fragen#${anchor}`}
      aria-label={`${String(children)} — ${t("dataHelp.label")}`}
      className="mt-2 inline-flex min-h-11 items-center gap-2 rounded-card text-ui font-semibold text-ink underline decoration-line underline-offset-4 hover:decoration-ink focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
    >
      <InfoIcon className="shrink-0 text-lead" />
      <span>{children}</span>
    </Link>
  );
}
