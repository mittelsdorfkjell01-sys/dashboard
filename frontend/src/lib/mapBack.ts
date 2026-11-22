import { useLocation, useNavigate } from "react-router-dom";

/**
 * The back control, identical on both halves of the public map. It steps back
 * in history, and falls back to the homepage when this tab has no entry to go
 * back to — a deep link, a reload or a new tab (`location.key === "default"`).
 *
 * The spot map did exactly this while the wind map always navigated to "/",
 * so the same glyph in the same corner lost your previous page depending on
 * which half of the map you happened to be looking at (2026-11-16).
 */
export function useMapBack(): () => void {
  const navigate = useNavigate();
  const location = useLocation();
  return () => {
    if (location.key !== "default") navigate(-1);
    else navigate("/");
  };
}
