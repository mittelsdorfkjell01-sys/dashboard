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
      contentStatus: "verified",
      contentReviewedAt: "2026-10-01T00:00:00Z",
      classificationReason: "Ein eigenständiges Reiseziel für mehrere Bedingungen.",
    })} />);
    expect(html).toContain("Eine Reise wert");
    expect(html).toContain("Community");
    expect(html).toContain("Lena K.");
    expect(html).toContain("Redaktionell geprüft");
    expect(html).toContain("Warum diese Einordnung?");
    expect(html).toContain("eigenständiges Reiseziel");
    expect(html).not.toContain("badge");
  });

  it("makes an unreviewed legacy entry explicit without showing its old rank", () => {
    const html = renderToStaticMarkup(<SpotEditorialClassification spot={spot({
      origin: "editorial",
      editorialClassification: "world_class",
      contentStatus: "unreviewed",
    })} />);
    expect(html).toContain("noch nicht redaktionell geprüft");
    expect(html).toContain("frühere Relevanzeinordnung");
    expect(html).not.toContain(">World Class<");
  });
});
