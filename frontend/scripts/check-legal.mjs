const required = [
  "VITE_LEGAL_OPERATOR",
  "VITE_LEGAL_STREET",
  "VITE_LEGAL_POSTAL_CITY",
  "VITE_LEGAL_COUNTRY",
  "VITE_LEGAL_EMAIL",
];

// The dedicated admin deployment contains no public/legal routes. Its release
// must therefore not depend on the separate public site's operator data.
if (process.env.VITE_INCLUDE_ADMIN === "true") {
  process.exit(0);
}

const missing = required.filter((key) => !process.env[key]?.trim());
if (process.env.VITE_LEGAL_REVIEW_APPROVED !== "true") {
  missing.push("VITE_LEGAL_REVIEW_APPROVED=true");
}
if (missing.length) {
  console.error(`Release blocked: legal review/data missing: ${missing.join(", ")}`);
  process.exit(1);
}
