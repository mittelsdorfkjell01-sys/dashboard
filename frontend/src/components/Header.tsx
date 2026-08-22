import { Link } from "react-router-dom";
import { Wordmark } from "./ui";
import AccountMenu from "./AccountMenu";

/**
 * Floating top bar shared by the map and search pages: brand centred, account
 * menu right. The Welle/Wind toggle was removed — the sport is chosen on the
 * results, not in the page chrome. The map hides the account menu (`showAccount
 * = false`) — its own close button already covers leaving the page.
 */
export default function Header({ showAccount = true }: { showAccount?: boolean }) {
  return (
    <header className="pointer-events-none absolute inset-x-0 top-0 z-[1000]">
      <div className="mx-auto max-w-[1400px] px-4 pt-4 sm:px-8 sm:pt-6">
        <div className="pointer-events-auto grid grid-cols-[1fr_auto_1fr] items-center gap-4">
          <span aria-hidden className="hidden sm:block" />

          <Link
            to="/"
            aria-label="surfwind data — Startseite"
            className="col-start-2 select-none justify-self-center leading-none"
          >
            <Wordmark size="md" />
          </Link>

          <div className="col-start-3 justify-self-end">
            {showAccount && <AccountMenu />}
          </div>
        </div>
      </div>
    </header>
  );
}
