import { useEffect } from "react";

interface PageMetaOptions {
  title: string;
  description: string;
  canonicalPath: string;
  robots?: "index,follow" | "noindex,follow";
  imagePath?: string;
}

const PUBLIC_SITE_ORIGIN = "https://surfwinddata.com";

function upsertMeta(selector: string, attributes: Record<string, string>) {
  let element = document.head.querySelector<HTMLMetaElement>(selector);
  const created = !element;
  if (!element) {
    element = document.createElement("meta");
    document.head.appendChild(element);
  }
  const previousContent = element.getAttribute("content");
  for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
  return { element, previousContent, created };
}

/** Keep route-level browser and crawler metadata in sync inside the public SPA. */
export function usePageMeta({
  title,
  description,
  canonicalPath,
  robots = "index,follow",
  imagePath = "/hero-surfwind-1280.jpg",
}: PageMetaOptions) {
  useEffect(() => {
    const canonicalUrl = new URL(canonicalPath, PUBLIC_SITE_ORIGIN).toString();
    const imageUrl = new URL(imagePath, PUBLIC_SITE_ORIGIN).toString();
    const previousTitle = document.title;
    const previousValues = [
      upsertMeta('meta[name="description"]', { name: "description", content: description }),
      upsertMeta('meta[name="robots"]', { name: "robots", content: robots }),
      upsertMeta('meta[property="og:title"]', { property: "og:title", content: title }),
      upsertMeta('meta[property="og:description"]', { property: "og:description", content: description }),
      upsertMeta('meta[property="og:type"]', { property: "og:type", content: "website" }),
      upsertMeta('meta[property="og:url"]', { property: "og:url", content: canonicalUrl }),
      upsertMeta('meta[property="og:image"]', { property: "og:image", content: imageUrl }),
      upsertMeta('meta[name="twitter:card"]', { name: "twitter:card", content: "summary_large_image" }),
      upsertMeta('meta[name="twitter:title"]', { name: "twitter:title", content: title }),
      upsertMeta('meta[name="twitter:description"]', { name: "twitter:description", content: description }),
    ];

    document.title = title;

    let canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (!canonical) {
      canonical = document.createElement("link");
      canonical.rel = "canonical";
      document.head.appendChild(canonical);
    }
    const previousCanonical = canonical.getAttribute("href");
    canonical.href = canonicalUrl;

    return () => {
      document.title = previousTitle;
      previousValues.forEach(({ element, previousContent, created }) => {
        if (created) element.remove();
        else if (previousContent === null) element.removeAttribute("content");
        else element.setAttribute("content", previousContent);
      });
      if (previousCanonical === null) canonical.removeAttribute("href");
      else canonical.setAttribute("href", previousCanonical);
    };
  }, [canonicalPath, description, imagePath, robots, title]);
}
