import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Spot } from "../../lib/types";
import SpotEditorialClassification from "../SpotEditorialClassification";

const spot = (over: Partial<Spot> = {}): Spot => ({
  id: "1", name: "Laboe", region: "Kiel", wind: 0, tags: [], image: "", ...over,
});

describe("SpotEditorialClassification", () => {
  it("shows classification and community credit as independent quiet metadata", () => {
    const html = renderToStaticMarkup(<SpotEditorialClassification spot={spot({
      origin: "community",
      contributorName: "Lena K.",
      editorialClassification: "worth_trip",
    })} />);
    expect(html).toContain("Eine Reise wert");
    expect(html).toContain("Community");
    expect(html).toContain("Lena K.");
    expect(html).not.toContain("badge");
  });

  it("renders nothing for an unranked editorial spot", () => {
    expect(renderToStaticMarkup(<SpotEditorialClassification spot={spot({ origin: "editorial" })} />)).toBe("");
  });
});
