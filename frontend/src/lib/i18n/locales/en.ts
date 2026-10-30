import type { de } from "./de";

type TranslationShape<T> = {
  [K in keyof T]: T[K] extends string ? string : TranslationShape<T[K]>;
};

/** English catalogue. `satisfies` keeps every public key in lockstep with German. */
export const en = {
  common: { loading: "Loading…", retry: "Try again", back: "Back", cancel: "Cancel", close: "Close", sending: "Sending…" },
  siteLinks: { faq: "Data & questions", contact: "Contact", about: "About the project", terms: "Terms of use", imprint: "Legal notice", privacy: "Privacy" },
  footer: { copyright: "© {{year}} surfwind data" },
  header: { searchPlaceholder: "Place, region or spot", tagline: "A clear view of the best surf spots", openSearch: "Open search", addSpots: "Add spots" },
  language: { label: "Language", german: "Deutsch", english: "English" },
  region: {
    notFound: "Region not found", overview: "Overview", backOverview: "Back to overview",
    spotCount_one: "{{count}} spot in this region", spotCount_other: "{{count}} spots in this region",
    descriptionPending: "The region description is still being reviewed.", verified: "Content reviewed",
    source: "Source for the region description", top: "Spot selection in {{name}}", when: "When to go",
    windUnknown: "Regional wind availability: unknown", windHelp: "Why is regional wind availability still unknown?",
    spots: "The spots", noSpots: "No spots match this selection.", map: "On the map", similar: "Similar regions",
  },
  dataHelp: { label: "Open explanation", suffix: "More under Data & questions" },
  recommendations: { limits: "Catalogue selection for orientation. Forecasts are model values, not guarantees; source and update time are shown with the weather data.", currentTitle: "Spot selection", nextWeekTitle: "Save for next week", seasonTitle: "Seasonal spot selection", allSpots: "Discover all spots", map: "Map" },
  faq: { title: "Data & questions", intro: "Help with spots, forecasts, data sources, your account and Surfwinddata.", open: "Still have a question?", contact: "Contact us" },
  trips: {
    title: "Trip planner", intro: "Plan dates, spots and preparation manually — without automated weather promises.",
    new: "New trip", emptyTitle: "No trip planned yet", emptyBody: "Create a trip and collect the spots you want to visit.",
    loadFailed: "Trips could not be loaded.", saveFailed: "The trip could not be saved.", deleteFailed: "The trip could not be deleted.", copyFailed: "The trip could not be copied.", shareFailed: "Sharing could not be changed.",
    name: "Trip name", start: "Start date", end: "End date", notes: "Notes", notesPlaceholder: "Travel, accommodation, local contacts …",
    spots: "Planned spots", spotSearch: "Search for a spot", search: "Search", noSearch: "No matching public spots found.", add: "Add", remove: "Remove",
    moveUp: "Move up", moveDown: "Move down", plannedDate: "Planned day", stopNotes: "Note for this stop",
    days: "Trip days", daysHint: "Notes stay private. A share link only includes them if you explicitly allow that later.",
    day: { notes: "Day note", accommodation: "Accommodation", travel: "Travel" },
    role: "Role", mainSpot: "Main spot", alternativeSpot: "Alternative", noDaySpots: "No spot has been added for this day yet.", openSpot: "Open spot", planSpot: "Add to trip plan",
    checklist: "Checklist", checklistPlaceholder: "e.g. pack wetsuit", addChecklist: "Add item",
    status: "Status", draft: "Draft", planned: "Planned", completed: "Completed", cancelled: "Cancelled",
    save: "Save trip", saving: "Saving …", cancel: "Cancel", edit: "Edit", copy: "Copy", share: "Copy link", revokeShare: "Stop sharing", sharedCopied: "The read-only link is active and has been copied.", delete: "Delete", confirmDelete: "Really delete?",
    contentChanged: "At least one saved spot has changed since planning or is no longer public. Please review it again.",
    sharedLabel: "Shared trip plan", sharedNotFound: "Trip plan unavailable", sharedNotFoundBody: "The link is invalid or has been revoked.", sharedManualNote: "This plan was assembled manually. Check current conditions, local rules and forecasts for each trip day.",
    dateError: "The end date cannot be before the start date.", manualNote: "Continue to check current forecasts and local advice before every day on the water.",
  },
  visits: {
    title: "Spots visited", add: "Mark as visited", added: "Marked as visited", remove: "Remove visit mark",
    emptyTitle: "No visited spots yet", emptyBody: "On a spot page, mark the places where you have actually been on the water.", discover: "Discover spots",
    loadFailed: "Visited spots could not be loaded.", actionFailed: "The visit could not be saved.", visitedOn: "Visited on {{date}}", feedback: "Feedback", outcome: "Was the visit worthwhile?", noOutcome: "No rating", worthwhile: "Worthwhile", neutral: "Neutral", notWorthwhile: "Not worthwhile", notes: "What matched the spot information, and what did not?", save: "Save feedback",
  },
  favorites: {
    title: "Saved", emptyTitle: "Nothing saved yet", emptyBody: "Use the bookmark on a spot to collect it here.", discover: "Discover spots",
    count_one: "{{count}} spot saved", count_other: "{{count}} spots saved", removeFailed: "The spot could not be removed. Please try again.", remove: "Remove {{name}} from saved spots", plan: "Plan",
    compare: "Compare spots", compareHint: "Only available structured details are compared. Missing values remain unknown.", property: "Property", sports: "Sports", level: "Level", water: "Water character", review: "Content review", region: "Region", verified: "Editorially reviewed", pending: "Review pending", unknown: "Unknown",
  },
  account: { loading: "Loading account …", unavailableTitle: "Account currently unavailable" },
  accountNav: { profile: "Profile", setup: "My setup", saved: "Saved", visited: "Spots visited", trips: "Trip planner", addSpots: "Add spots", settings: "Settings" },
  menu: {
    trigger: "Account menu", account: "Account", close: "Close menu", areas: "Account sections",
    myProfile: "My profile", welcome: "Welcome", welcomeBody: "Sign in to manage favourites and your own spots.",
    signIn: "Sign in", createAccount: "Create account", planned: "Planned", signOut: "Sign out", signOutSheet: "sign out",
  },
  settings: {
    pageTitle: "Settings", planned: "Planned",
    units: {
      title: "Units & display", description: "Your selection applies wherever wind, wave height, temperature and distance are shown.",
      wind: "Wind", wave: "Wave height", temp: "Temperature", distance: "Distance",
      preview: "Preview: wind {{wind}} · wave {{wave}} · water {{water}} · station {{station}}", saving: "Saving units …",
    },
    account: { title: "Account", description: "Your personal details and password." },
    profile: { name: "Display name", submit: "Save", submitting: "Saving …", saved: "Profile saved.", failed: "Could not save." },
    email: {
      heading: "Change email address", current: "Current: {{email}}", pending: " · Confirmation pending for {{email}}",
      newLabel: "New email address", currentPassword: "Current password", submit: "Send confirmation link", submitting: "Sending …",
      sent: "A confirmation link was sent to the new email address. Your current address remains valid until confirmation.", failed: "Could not change the address.",
    },
    password: {
      heading: "Change password", current: "Current password", new: "New password", hint: "At least 8 characters.",
      submit: "Change password", submitting: "Changing …", changed: "Password changed.", failed: "Could not change password.",
    },
    privacy: {
      title: "Privacy & content", description: "Control the visibility of your profile, contributions and account data.",
      plannedNote: "A public profile and per-post visibility will follow once this content is stored and moderated on the server. Until then your account is private — only you can see your favourites and suggestions.",
      dataHeading: "Your data", dataBody: "Download a copy of your account data or permanently delete your account.",
      exportSubmit: "Download data export", exporting: "Creating export …", exportFailed: "The data export failed. Please try again.",
      deleteSubmit: "Delete account", deleteTitle: "Permanently delete account", deleteBody: "Favourites will be deleted. Published contributions remain in anonymised form.",
      deletePassword: "Password for confirmation", deleteConfirm: "Delete permanently", deleting: "Deleting …", deleteFailed: "The account could not be deleted.",
      discardTitle: "Cancel deletion?", discardMessage: "The entered password will be discarded.", discardConfirm: "Discard",
    },
    notifications: {
      title: "Notifications", description: "Choose which messages you want to receive about your suggestions.",
      plannedNote: "Email notifications are not currently available. Once delivery is set up, you can be informed here about decisions on your suggestions.",
      submissionEmails: "Email me when a decision is made on my spot suggestion", saveFailed: "The setting could not be saved.",
      alertsNote: "Weather alerts for favourites will follow once reliable thresholds and delivery times are defined.",
    },
  },
  setup: {
    pageTitle: "My setup", intro: "Manage your kite setup and riding preferences. The detailed setup feature currently focuses on kitesurfing.",
    loading: "Loading setup …", loadFailed: "Your setup could not be loaded.", saveFailed: "Could not save. Please try again.",
    submit: "Save setup", submitting: "Saving …", incomplete: "Still needed: weight, level or kite.", required: "Required", optional: "Optional", choose: "Please choose", unitKg: "kg", unitKm: "km",
    basics: { title: "Basics", intro: "Weight, level and one kite are enough to get started.", weight: "Weight", level: "Kite level" },
    gear: { title: "Your equipment", intro: "Add your active kites and board type." },
    style: { title: "Riding style", weighting: "{{style}} weighting", intro: "Set how important each style is to you: 0 means unimportant, 3 means especially important." },
    water: { title: "Water", intro: "Optional: choose the conditions you particularly enjoy." },
    travel: { title: "On the road", intro: "Home location and travel mode are optional and can be changed at any time.", lat: "Latitude", lon: "Longitude", home: "Home location", mode: "Travel mode", maxDistance: "Maximum distance", dayTrip: "Day trip", weekend: "Weekend", trip: "Trip", camper: "Camper" },
    levels: { beginner: "Beginner", advanced: "Advanced", expert: "Expert", competition: "Competition" },
    styles: { freeride: "Freeride", freestyle: "Freestyle", bigAir: "Big Air", waveRiding: "Wave riding", wavekite: "Wave kite" },
    waterKinds: { flach: "Flat water", chop: "Chop", welleKlein: "Small waves", welleGross: "Large waves", tiefesWasser: "Deep water" },
  },
  community: {
    commons: { badge: "Commons", full: "From Wikimedia Commons" },
    license: { confirm: "I confirm the", linkLabel: "rights and consent declaration", version: " ({{version}})" },
    gallery: { enlarge: "Enlarge image", enlargeCredited: "Enlarge image — {{credit}}", viewAll: "View all {{count}} images", addPhotos: "Add photos", suggestHero: "Suggest cover image", emptyTitle: "No image available yet", uploadAria: "Upload images" },
    composer: {
      prompt: "How was {{spot}}?", starsAria: "{{count}} stars", textPlaceholder: "What were the conditions like? What should others know? (required)",
      sport: "Sport", level: "Level", visitDate: "Visit date", namePlaceholder: "First name or full name (required)", submit: "Publish",
      errStars: "Please choose a star rating.", errText: "Please briefly describe your experience.", errName: "Please enter your first name (or full name).",
      errLicense: "Please confirm the rights declaration for the photo.", sendFailed: "Could not send.",
    },
    feed: { emptyTitle: "Be the first to report from here.", emptyBody: "Helpful contributions mention conditions, level and what others should know on site.", sortNewest: "Newest", sortHelpful: "Most helpful" },
    post: { helpful: "Helpful", helpfulCounted: "Helpful · {{count}}", moreActions: "More actions", report: "Report" },
    lightbox: { label: "Large image gallery", prev: "Previous image", next: "Next image" },
    report: {
      title: "Report image", thanks: "Thank you, your report has been received.", contact: "For urgent rights issues: {{contact}}", notePlaceholder: "Note (optional)", submit: "Report", failed: "Report failed.",
      reasons: { copyright: "Copyright / my image", inappropriate: "Inappropriate", wrongSpot: "Wrong spot", other: "Other" },
    },
    upload: {
      title: "Add image", note: "It is uploaded immediately, but only becomes visible to everyone after a short review.", removeImage: "Remove image", pick: "Choose image", formats: "JPG, PNG or WebP", creditPlaceholder: "Credit: name or Instagram (optional)", submit: "Upload", submitting: "Uploading…", queued: "Thank you! Your image is awaiting approval.", failed: "Upload failed.",
    },
    hero: { title: "Suggest cover image", requirements: "At least {{width}}×{{height}} px, landscape, JPG/PNG/WebP.", submit: "Suggest", queued: "Thank you! Your cover image suggestion is awaiting approval.", invalid: "The image does not meet the cover requirements." },
  },
} satisfies TranslationShape<typeof de>;
