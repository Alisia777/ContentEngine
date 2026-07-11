# ALTEA Motion UI Kit

ALTEA Motion is a local FastAPI/Jinja prototype for a premium animated interface. It uses only local CSS, JavaScript, and SVG assets. It does not implement real authentication, credentials, paid providers, external account registration, or external CDN assets.

## Design Principles

- Deep black and charcoal surfaces with warm gold and ivory accents.
- Calm luxury motion: slow petals, soft ribbon flow, staggered reveal, subtle shimmer.
- Minimal, readable dashboard density without noisy visual effects.
- UI elements are code-built, not static PNG screenshots.
- Reduced-motion users keep the core UI and lose decorative animation.

## Routes

- `/altea-motion` redirects to `/altea-motion/splash`.
- `/altea-motion/splash` shows the animated startup screen.
- `/altea-motion/login` shows the dynamic login prototype.
- `/altea-motion/auth-loading` shows staged post-login access checks.
- `/altea-motion/dashboard-loading` shows a premium skeleton loading state.
- `/altea-motion/dashboard` shows the final ALTEA dashboard.

## Motion Rules

- Use transform and opacity for most animation.
- Keep gold shimmer slow and quiet.
- Do not add neon, noisy particles, or game-like motion.
- Respect `prefers-reduced-motion` by disabling petal drift, ribbon flow, skeleton shimmer, and chart drawing.

## Components And Classes

- `.altea-shell` / `.altea-dashboard-shell` for page layout.
- `.altea-bg`, `.altea-petal`, `.altea-bg__ribbon` for the animated background.
- `.altea-card` for glass luxury cards.
- `.altea-glow-button` for primary actions.
- `.altea-input-wrap` for labeled form fields.
- `.altea-progress` and `.altea-auth-steps` for staged flows.
- `.altea-loader-ring` for access checks.
- `.altea-skeleton` for loading placeholders.
- `.altea-sidebar`, `.altea-kpi-card`, `.altea-chart`, `.altea-product-table` for dashboard modules.

## Local Assets

The prototype uses local SVG files in `app/static/altea_motion/assets/`:

- `logo_mark.svg`
- `altea_flower.svg`
- `petal.svg`
- `light_ribbon.svg`

These are decorative and reusable. The core UI remains HTML/CSS/Jinja.

## How To Run

```powershell
python -m uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8014/altea-motion/splash
http://127.0.0.1:8014/altea-motion/login
http://127.0.0.1:8014/altea-motion/auth-loading
http://127.0.0.1:8014/altea-motion/dashboard-loading
http://127.0.0.1:8014/altea-motion/dashboard
```

## Verification

```powershell
python -m pytest -q
```

The tests verify that all five screens render, static assets exist, Russian labels are present, no external CDN assets are used, and reduced-motion CSS exists.

## Extension Notes

Future work can connect the dashboard panels to real brand metrics, but this prototype intentionally keeps auth and business logic mocked. Add new ALTEA screens by reusing the same base template, local tokens, and motion classes.
