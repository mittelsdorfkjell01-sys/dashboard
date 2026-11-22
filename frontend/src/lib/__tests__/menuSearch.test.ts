import { describe, expect, it } from "vitest";

import { de } from "../i18n/locales/de";
import type { TranslationKey } from "../i18n";
import { buildMenuSearchIndex, normalize, searchMenu } from "../menuSearch";
import { DATENSCHUTZ_SECTIONS, HELP_JUMP, IMPRESSUM_SECTIONS, TERMS_SECTIONS } from "../infoSections";

// The i18n runtime needs a DOM; resolving straight from the German catalogue
// is all the index needs.
const t = (key: TranslationKey) =>
  key.split(".").reduce<unknown>((node, part) => (node as Record<string, unknown>)[part], de) as string;
const index = buildMenuSearchIndex(t);

describe("menu search", () => {
  it("indexes every section of the info and legal pages", () => {
    const targets = new Set(index.map((e) => e.to));
    for (const s of HELP_JUMP) expect(targets).toContain(`/fragen#${s.id}`);
    for (const s of IMPRESSUM_SECTIONS) expect(targets).toContain(`/impressum#${s.id}`);
    for (const s of TERMS_SECTIONS) expect(targets).toContain(`/nutzungsbedingungen#${s.id}`);
    for (const s of DATENSCHUTZ_SECTIONS) expect(targets).toContain(`/datenschutz#${s.id}`);
  });

  it("finds a legal section by a word of its heading, without its number", () => {
    const [first] = searchMenu(index, "cookies");
    expect(first.to).toBe("/datenschutz#cookies");
    expect(first.label).toBe("Cookies und lokale Speicherung");
    expect(first.context).toBe("Datenschutz");
  });

  it("puts the page itself above its sections", () => {
    expect(searchMenu(index, "Impressum")[0].to).toBe("/impressum");
  });

  it("finds a feature by a keyword that is not in its label", () => {
    expect(searchMenu(index, "knoten").map((e) => e.to)).toContain("/konto/einstellungen");
  });

  it("ignores case, accents and ß", () => {
    expect(normalize("Übermittlung Straße")).toBe("ubermittlung strasse");
    expect(searchMenu(index, "ubermittlung")[0].to).toBe("/datenschutz#drittlaender");
  });

  it("needs every word of the query", () => {
    expect(searchMenu(index, "cookies passwort")).toHaveLength(0);
    expect(searchMenu(index, "   ")).toHaveLength(0);
  });
});
