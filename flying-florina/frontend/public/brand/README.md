# Brand assets

This folder holds Flying_Florina branding. **No portrait or likeness is included**: the
user-authorized photo and generated portrait referenced in the build specification
(`Screenshot 2025-05-11 132555(1).png`, `a_polished_high_end_circular_logo_branding_portr.png`,
`wide_high_res_futuristic_ui_dashboard_screenshot.png`, `a_polished_modern_product_ui_marketing_hero_scree.png`)
were not available in this build environment, so a neutral placeholder mark (`ff-mark.svg`) is used.
We did not fabricate a likeness.

To use the authorized assets locally (they stay on your machine; nothing is uploaded):

1. Copy the circular logo/portrait to `frontend/public/brand/florina-logo.png`.
2. Optionally copy a hero image to `frontend/public/brand/florina-hero.png`.
3. Record provenance in `PROVENANCE.md` (source, date, authorization).

The UI loads `florina-logo.png` when present and falls back to `ff-mark.svg` otherwise.
The generated composite should not be described as an exact photographic reproduction.
IFS trademarks/logos are not included; set `BRAND_ASSETS_AUTHORIZED=true` only for assets you are licensed to use.
