# Security exceptions

## React Router RSC advisory

`react-router-dom` is pinned to the newest published release. The remaining npm
advisory `GHSA-qwww-vcr4-c8h2` applies to React Server Components action handling.
This project is a client-only Vite SPA and does not enable RSC or Router actions,
so the vulnerable path is not present. CI still fails on any critical npm issue;
remove this exception and restore a high-severity gate as soon as npm publishes
a fixed React Router release.
