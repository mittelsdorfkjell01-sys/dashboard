/// <reference types="vite/client" />

declare const __INCLUDE_ADMIN__: boolean;
declare const __ADMIN_DEPLOY__: boolean;
// CARTO basemap key, resolved at build time from the environment (see
// vite.config.ts). Empty string = keyless tiles.
declare const __CARTO_KEY__: string;
