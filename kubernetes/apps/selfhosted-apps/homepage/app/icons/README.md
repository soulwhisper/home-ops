# Locally served icons

These files back every `icon: /icons/<name>.svg` reference (route annotations
and the homepage ConfigMap). They are mounted into the homepage pod at
`/app/public/icons` via the `homepage-icons` ConfigMap (see
`../kustomization.yaml` — generator file list is explicit, no globs).

## Sources / where to get more

- https://dashboardicons.com/ (homarr-labs/dashboard-icons) — primary source
- https://simpleicons.org/ — `si-*` icons; add `fill="#ffffff"` to the `<svg>`
  root (homepage previously colored them via CSS mask; dashboard theme is dark)
- https://pictogrammers.com/library/mdi/ — mdi set

## Rules

- **SVG only.** Flux source-controller and flate's ignoreFS default-exclude
  `*.png`/`*.jpg`/... raster files (home-operations/flate#998). Raster-only
  icons ship as an SVG wrapper embedding the PNG as a data URI
  (see `foundry-vtt.svg`, `scrypted.svg`, `sillytavern.svg`).
- Keep the generator `files:` list in `../kustomization.yaml` in sync when
  adding/removing icons (glob patterns are not supported there).
- Adding an icon goes live on merge: flux updates the ConfigMap, reloader
  restarts homepage, Next rescans `public/` at boot.
