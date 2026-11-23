/**
 * One-shot request to reopen the account menu.
 *
 * A page the visitor reached *from* that menu (the site links in it) carries a
 * back control, and "back" there means back into the menu, not just onto the
 * previous page with the menu shut. The menu's open state is local to the
 * component and the component unmounts with the route, so the request travels
 * through sessionStorage: it survives the history navigation, belongs to this
 * tab only, and is consumed by the first menu that mounts afterwards.
 *
 * Deliberately not navigation state: the back step restores a *previous*
 * history entry, whose state was written when that entry was created and
 * cannot be amended on the way back.
 */
const KEY = "swd.account-menu-return";

/** Ask the next account menu that mounts to open itself. */
export function requestAccountMenu(): void {
  try {
    sessionStorage.setItem(KEY, "1");
  } catch {
    /* private browsing — the back step then simply lands on the page */
  }
}

/** Take the pending request, if any. Reading it clears it. */
export function consumeAccountMenuRequest(): boolean {
  try {
    if (!sessionStorage.getItem(KEY)) return false;
    sessionStorage.removeItem(KEY);
    return true;
  } catch {
    return false;
  }
}
