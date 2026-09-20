/** Up to two uppercase initials from a display name, falling back to the first
 *  letter of the email, then a neutral placeholder. Used for the account avatar
 *  wherever no uploaded profile picture exists yet. */
export function initialsOf(displayName?: string | null, email?: string | null): string {
  const fromName = (displayName ?? "")
    .split(/\s+/)
    .map((part) => part[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
  if (fromName) return fromName;
  const fromEmail = (email ?? "")[0]?.toUpperCase();
  return fromEmail || "·";
}
