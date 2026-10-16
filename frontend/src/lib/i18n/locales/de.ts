/**
 * German message catalogue — the source language.
 *
 * Structure mirrors the UI surfaces rather than the component tree: a string
 * that appears in several components still belongs under one surface key, and
 * moving a component between files must never force a key rename. `common`
 * holds the handful of words that genuinely recur across surfaces.
 *
 * This catalogue only ever contains strings that are actually referenced from
 * a migrated component. It grows one tranche at a time; speculative keys for
 * surfaces nobody has migrated yet would rot silently, because nothing fails
 * when an unused key drifts out of sync with the screen it was meant for.
 *
 * `as const` is load-bearing: it turns every key into a literal type, which is
 * what lets `t()` reject a typo at compile time (see ../i18next.d.ts). Keep the
 * object literal inline — extracting a sub-object into a `let` widens it to
 * `string` and silently loses that checking.
 *
 * Only the public site lives here. The admin back office stays hard-coded in
 * German on purpose: it ships in a separate chunk (scripts/check-bundle.mjs
 * fails the public build if an admin chunk leaks in), and routing its strings
 * through this catalogue would pull them into the public bundle for an
 * audience of operators who will never need another language.
 */
export const de = {
  common: {
    loading: "Lädt…",
    retry: "Erneut versuchen",
    back: "Zurück",
    cancel: "Abbrechen",
    close: "Schließen",
    sending: "Senden…",
  },
  // Rendered by both the footer and the account menu — see lib/siteLinks.ts,
  // which owns the routes and their order.
  siteLinks: {
    faq: "Fragen und Antworten",
    contact: "Kontakt",
    about: "Über das Projekt",
    terms: "Nutzungsbedingungen",
    imprint: "Impressum",
    privacy: "Datenschutz",
  },
  footer: {
    copyright: "© {{year}} surfwind data",
  },
  header: {
    searchPlaceholder: "Ort, Region oder Spot",
  },
  account: {
    loading: "Konto wird geladen …",
    unavailableTitle: "Konto derzeit nicht erreichbar",
  },
  accountNav: {
    profile: "Profil",
    setup: "Mein Setup",
    saved: "Saved",
    visited: "Spots besucht",
    addSpots: "Spots hinzufügen",
    settings: "Einstellungen",
  },
  menu: {
    trigger: "Kontomenü",
    account: "Konto",
    close: "Menü schließen",
    areas: "Konto-Bereiche",
    myProfile: "Mein Profil",
    welcome: "Willkommen",
    welcomeBody: "Melde dich an, um Favoriten und eigene Spots zu verwalten.",
    signIn: "Anmelden",
    createAccount: "Konto erstellen",
    signOut: "Abmelden",
    // The mobile sheet sets its rows in lower case; keeping it a separate key
    // means a future locale can diverge without one of the two going wrong.
    signOutSheet: "abmelden",
  },
  settings: {
    pageTitle: "Einstellungen",
    planned: "Geplant",
    units: {
      title: "Einheiten & Anzeige",
      description:
        "Deine Auswahl gilt überall auf der Seite, wo Wind, Wellenhöhe, Temperatur und Entfernungen angezeigt werden.",
      wind: "Wind",
      wave: "Wellenhöhe",
      temp: "Temperatur",
      distance: "Entfernung",
      preview: "Vorschau: Wind {{wind}} · Welle {{wave}} · Wasser {{water}} · Station {{station}}",
      saving: "Einheiten werden gespeichert …",
    },
    account: {
      title: "Konto",
      description: "Deine persönlichen Angaben und dein Passwort.",
    },
    profile: {
      name: "Anzeigename",
      submit: "Speichern",
      submitting: "Speichere …",
      saved: "Profil gespeichert.",
      failed: "Speichern fehlgeschlagen.",
    },
    email: {
      heading: "E-Mail-Adresse ändern",
      current: "Aktuell: {{email}}",
      pending: " · Bestätigung ausstehend für {{email}}",
      newLabel: "Neue E-Mail-Adresse",
      currentPassword: "Aktuelles Passwort",
      submit: "Bestätigungslink senden",
      submitting: "Sende …",
      sent: "Bestätigungslink an die neue E-Mail-Adresse gesendet. Bis zur Bestätigung bleibt deine bisherige Adresse gültig.",
      failed: "Adresswechsel fehlgeschlagen.",
    },
    password: {
      heading: "Passwort ändern",
      current: "Aktuelles Passwort",
      new: "Neues Passwort",
      hint: "Mindestens 8 Zeichen.",
      submit: "Passwort ändern",
      submitting: "Ändere …",
      changed: "Passwort geändert.",
      failed: "Ändern fehlgeschlagen.",
    },
    privacy: {
      title: "Privatsphäre & Inhalte",
      description: "Steuere die Sichtbarkeit deines Profils und deiner Beiträge sowie deine Kontodaten.",
      plannedNote:
        "Ein öffentliches Profil und die Sichtbarkeit einzelner Beiträge folgen, sobald diese Inhalte serverseitig gespeichert und moderiert werden. Dein Konto ist bis dahin privat — nur du siehst deine Favoriten und Vorschläge.",
      dataHeading: "Deine Daten",
      dataBody: "Lade eine Kopie deiner Kontodaten herunter oder lösche dein Konto endgültig.",
      exportSubmit: "Datenexport herunterladen",
      exporting: "Export wird erstellt …",
      exportFailed: "Datenexport fehlgeschlagen. Bitte versuche es erneut.",
      deleteSubmit: "Konto löschen",
      deleteTitle: "Konto endgültig löschen",
      deleteBody: "Favoriten werden gelöscht. Veröffentlichte Beiträge bleiben anonymisiert erhalten.",
      deletePassword: "Passwort zur Bestätigung",
      deleteConfirm: "Endgültig löschen",
      deleting: "Lösche …",
      deleteFailed: "Konto konnte nicht gelöscht werden.",
      discardTitle: "Löschung abbrechen?",
      discardMessage: "Das eingegebene Passwort wird verworfen.",
      discardConfirm: "Verwerfen",
    },
    notifications: {
      title: "Benachrichtigungen",
      description: "Wähle, welche Nachrichten du zu deinen Vorschlägen erhalten möchtest.",
      plannedNote:
        "E-Mail-Benachrichtigungen sind derzeit nicht verfügbar. Sobald der Versand eingerichtet ist, kannst du hier über Entscheidungen zu deinen Vorschlägen informiert werden.",
      submissionEmails: "E-Mail bei Entscheidung über meinen Spot-Vorschlag",
      saveFailed: "Einstellung konnte nicht gespeichert werden.",
      alertsNote: "Wetteralarme für Favoriten folgen, sobald zuverlässige Schwellen und Versandzeiten feststehen.",
    },
  },
  setup: {
    pageTitle: "Mein Setup",
    intro:
      "Verwalte dein Kite-Setup und deine Fahrvorlieben. Die detaillierte Setup-Funktion ist derzeit auf Kitesurfen ausgerichtet.",
    loading: "Setup wird geladen …",
    loadFailed: "Dein Setup konnte nicht geladen werden.",
    saveFailed: "Speichern fehlgeschlagen. Bitte versuche es erneut.",
    submit: "Setup speichern",
    submitting: "Speichert …",
    incomplete: "Noch offen: Gewicht, Level oder Kite.",
    required: "Pflichtfeld",
    optional: "Optional",
    choose: "Bitte wählen",
    unitKg: "kg",
    unitKm: "km",
    basics: {
      title: "Grundangaben",
      intro: "Gewicht, Level und ein Kite reichen für den Start.",
      weight: "Gewicht",
      level: "Kite-Level",
    },
    gear: {
      title: "Deine Ausrüstung",
      intro: "Trage deine aktiven Kites und den Board-Typ ein.",
    },
    style: {
      title: "Fahrstil",
      weighting: "{{style}} Gewichtung",
      intro:
        "Stelle für jeden Stil ein, wie wichtig er dir ist: 0 steht für unwichtig, 3 für besonders wichtig.",
    },
    water: {
      title: "Wasser",
      intro: "Optional: Wähle die Bedingungen, die du besonders gern fährst.",
    },
    travel: {
      title: "Unterwegs",
      intro: "Heimatort und Reisemodus sind optional und jederzeit änderbar.",
      lat: "Breitengrad",
      lon: "Längengrad",
      home: "Heimatort",
      mode: "Reisemodus",
      maxDistance: "Maximale Entfernung",
      dayTrip: "Tagesausflug",
      weekend: "Wochenende",
      trip: "Reise",
      camper: "Camper",
    },
    // Rider levels and the style/water lists. Several of these are sport terms
    // that read the same in English ("Freeride", "Big Air", "Chop"); they still
    // live here, because whether a term travels is a translator's call, not
    // ours, and one rule ("visible text lives in the catalogue") beats an
    // exception list nobody will remember.
    levels: {
      beginner: "Einsteiger",
      advanced: "Fortgeschritten",
      expert: "Experte",
      competition: "Competition",
    },
    styles: {
      freeride: "Freeride",
      freestyle: "Freestyle",
      bigAir: "Big Air",
      waveRiding: "Wave Riding",
      wavekite: "Wavekite",
    },
    waterKinds: {
      flach: "Flachwasser",
      chop: "Chop",
      welleKlein: "Kleine Welle",
      welleGross: "Große Welle",
      tiefesWasser: "Tiefes Wasser",
    },
  },
  community: {
    commons: {
      badge: "Commons",
      full: "Aus Wikimedia Commons",
    },
    // The licence confirmation wraps a button in running text, so it stays three
    // keys rather than one: a sentence with embedded markup would need <Trans>,
    // and the trailing full stop is punctuation the lint guard already allows.
    license: {
      confirm: "Ich bestätige die",
      linkLabel: "Rechte- & Einwilligungserklärung",
      version: " ({{version}})",
    },
    gallery: {
      enlarge: "Bild vergrößern",
      enlargeCredited: "Bild vergrößern — {{credit}}",
      viewAll: "Alle {{count}} Bilder ansehen",
      addPhotos: "Bilder hinzufügen",
      suggestHero: "Titelbild vorschlagen",
      emptyTitle: "Aktuell noch kein Bild vorhanden",
      uploadAria: "Bilder hochladen",
    },
    composer: {
      prompt: "Wie war's am {{spot}}?",
      starsAria: "{{count}} Sterne",
      textPlaceholder: "Wie waren die Bedingungen? Was sollten andere wissen? (Pflichtfeld)",
      sport: "Sportart",
      level: "Level",
      visitDate: "Besuchsdatum",
      namePlaceholder: "Vorname oder Vor- und Nachname (Pflichtfeld)",
      submit: "Veröffentlichen",
      errStars: "Bitte eine Sternebewertung wählen.",
      errText: "Bitte kurz schreiben, wie es war.",
      errName: "Bitte Vorname (oder Vor- und Nachname) angeben.",
      errLicense: "Bitte die Rechteerklärung fürs Foto bestätigen.",
      sendFailed: "Senden fehlgeschlagen.",
    },
    feed: {
      emptyTitle: "Sei der Erste, der von hier berichtet.",
      emptyBody: "Hilfreiche Beiträge nennen Bedingungen, Level und was andere vor Ort wissen sollten.",
      sortNewest: "Neueste",
      sortHelpful: "Hilfreichste",
    },
    post: {
      helpful: "Hilfreich",
      helpfulCounted: "Hilfreich · {{count}}",
      moreActions: "Weitere Aktionen",
      report: "Melden",
    },
    lightbox: {
      label: "Bildergalerie, groß",
      prev: "Vorheriges Bild",
      next: "Nächstes Bild",
    },
    report: {
      title: "Bild melden",
      thanks: "Danke, deine Meldung ist eingegangen.",
      contact: "Bei dringenden Rechtefragen: {{contact}}",
      notePlaceholder: "Anmerkung (optional)",
      submit: "Melden",
      failed: "Meldung fehlgeschlagen.",
      reasons: {
        copyright: "Urheberrecht / mein Bild",
        inappropriate: "Unangemessen",
        wrongSpot: "Falscher Spot",
        other: "Sonstiges",
      },
    },
    upload: {
      title: "Bild hinzufügen",
      note: "Wird sofort hochgeladen, ist aber erst nach kurzer Prüfung für alle sichtbar.",
      removeImage: "Bild entfernen",
      pick: "Bild auswählen",
      formats: "JPG, PNG oder WebP",
      creditPlaceholder: "Credit: Name oder Instagram (optional)",
      submit: "Hochladen",
      submitting: "Hochladen…",
      queued: "Danke! Dein Bild wartet auf Freigabe.",
      failed: "Upload fehlgeschlagen.",
    },
    hero: {
      title: "Titelbild vorschlagen",
      requirements: "Mind. {{width}}×{{height}} px, Querformat, JPG/PNG/WebP.",
      submit: "Vorschlagen",
      queued: "Danke! Dein Titelbild-Vorschlag wartet auf Freigabe.",
      invalid: "Bild erfüllt die Hero-Vorgaben nicht.",
    },
  },
} as const;
