# Proofpage homepage

Buildless HTML, CSS, and JavaScript for https://proofpage.app. No package install, framework, external fonts, tracking, or environment variables are required.

Preview from the repository root with `python3 -m http.server 8891 --directory website`.

Deploy the contents of this folder to the existing Vercel `proofpage` project. `vercel.json` deliberately overrides the project's older Next.js settings. Verify a preview, then deploy to production. Keep release links and signing statements aligned with verified public release assets; do not advertise an unpublished build.

The hero is an interactive field terminal: Capture, Check, and Replay use real command names with clearly illustrative output. Commands type once, outputs follow, and a Canvas character field falls behind a receipt illustration. Run again replays the selected workflow. Pause motion and the operating system's reduced-motion setting show the complete transcript without continuous motion. Canvas and typing stop when the workbench is outside the viewport or the tab is hidden.

The product gallery contains real app screenshots and an 18-second silent animated tour. It is explicitly described as an animated tour, not a continuous screen recording. The H.264 MP4 is click-to-play, does not preload, and includes WebVTT captions and a text walkthrough. Rebuild it with `python scripts/render_homepage_tour.py` on macOS with Pillow and ffmpeg installed. Newsreader and JetBrains Mono are served locally with their OFL notices in `fonts/`.

See [design decisions and research](DESIGN.md) for the motion approach and alternatives considered. Browser acceptance covers workflow switching and typing, pause/resume, both themes, app views and video, all four platform choices, copy commands, narrow layouts, documentation, and current public release links.
