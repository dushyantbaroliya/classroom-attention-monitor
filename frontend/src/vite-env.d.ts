/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "true" in the static GitHub Pages demo build (see .env.demo). */
  readonly VITE_DEMO_STATIC?: string;
  /** Subpath the demo is served from, e.g. "/classroom-attention-monitor/". */
  readonly VITE_BASE_PATH?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv & { readonly BASE_URL: string };
}
