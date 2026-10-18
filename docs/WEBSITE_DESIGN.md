# Website motion choices

Research reviewed official documentation for [Motion's JavaScript animation API](https://motion.dev/docs/animate), [GSAP ScrollTrigger](https://gsap.com/docs/v3/Plugins/ScrollTrigger/), and [Playwright authentication state](https://playwright.dev/python/docs/auth).

Motion is a good optional choice for orchestrated DOM/SVG sequences. GSAP ScrollTrigger is useful for complex scroll timelines. Neither is needed for this site's current typing, falling glyphs, screenshot previews, and hover transitions: locally bundled JavaScript and CSS keep the site buildless, avoid CDN dependency, and make reduced-motion and pause behavior easy to inspect. Do not add scroll hijacking or a 3D library merely for decoration.

Real application screenshots replace invented product graphics. Screenshots open at full size in a keyboard-dismissable dialog. Text remains selectable, scroll remains native, and effects stop when paused, hidden, or reduced-motion is requested. Source material and user evidence are never sent to an animation provider.

Playwright's documentation warns that saved authentication state can impersonate the user. The browser companion therefore uses an explicit text export from the user's existing browser and does not persist authentication state.
