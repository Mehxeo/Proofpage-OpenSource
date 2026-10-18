# Proofpage homepage

Buildless HTML, CSS, and JavaScript for https://proofpage.app. No package install, framework, external fonts, tracking, or environment variables are required.

Preview from the repository root with `python3 -m http.server 8891 --directory website`.

Deploy the contents of this folder to the existing Vercel `proofpage` project. `vercel.json` deliberately overrides the project's older Next.js settings. Verify a preview, then deploy to production. Keep release links and signing statements aligned with verified public release assets; do not advertise an unpublished build.

The homepage includes an 18-second silent animated tour made from actual app screenshots. It is explicitly described as an animated tour, not a continuous screen recording. The H.264 MP4 is click-to-play, uses metadata-only preloading, and includes WebVTT captions and a text walkthrough. Rebuild it with `python scripts/render_homepage_tour.py` on macOS with Pillow and ffmpeg installed. The terminal is a labeled illustrative animation, never a live collection request.
