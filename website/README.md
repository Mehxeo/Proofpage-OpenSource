# Proofpage homepage

Buildless HTML, CSS, and JavaScript for https://proofpage.app. No package install, framework, external fonts, tracking, or environment variables are required.

Preview from the repository root with `python3 -m http.server 8891 --directory website`.

Deploy the contents of this folder to the existing Vercel `proofpage` project. `vercel.json` deliberately overrides the project's older Next.js settings. Verify a preview, then deploy to production. Keep release links and signing statements aligned with verified public release assets; do not advertise an unpublished build.

The hero is a forest of paper notes connected to a workspace. Select a leaf to
inspect a source type and open its guide. The SVG paths grow once, leaves breathe,
and the canopy responds slightly to a mouse; keyboard and touch need no hover.
Directly below, the interactive terminal keeps Capture, Check, and Replay with
real command names and clearly illustrative output. Pause motion and the system's
reduced-motion setting stop the effects. Forest and terminal visibility are
tracked separately; hidden and offscreen scenes stop their work.

A folded paper airplane flies through the hero, then gently follows a mouse
with a short fading trail. Throw again relaunches it. It does not intercept
clicks or replace the cursor. Touch and reduced-motion modes park it in the
forest, and Pause motion controls it together with the terminal. Its animation
loop sleeps when settled or the page is hidden. `paper-plane.js` is standalone
vanilla JavaScript; no runtime dependency or camera access is needed.

The product gallery contains real app screenshots and an 18-second silent animated tour. It is explicitly described as an animated tour, not a continuous screen recording. The H.264 MP4 is click-to-play, does not preload, and includes WebVTT captions and a text walkthrough. Rebuild it with `python scripts/render_homepage_tour.py` on macOS with Pillow and ffmpeg installed. IBM Plex Sans and JetBrains Mono are served locally with their OFL notices in `fonts/`. Four additional screenshots show setup, context review, MCP and Settings; the page clearly identifies the upcoming release preview.

See [design decisions and research](DESIGN.md) for the motion approach and alternatives considered. Browser acceptance covers workflow switching and typing, pause/resume, both themes, app views and video, all four platform choices, copy commands, narrow layouts, documentation, and current public release links.
