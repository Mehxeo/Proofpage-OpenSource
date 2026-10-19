# A forest of notes, October 2026

Proofpage should feel like a working instrument for investigating sources. The homepage puts one interactive object in the hero, then shows the real product. A paper receipt, source revisions, visible command output, and a restrained character field carry that idea through the page. No pill above the headline, invented customer logos, fake usage metrics, or scroll hijacking.

The new hero makes the archive tangible: four paper leaves grow from paths into
one workspace. Select a page, PDF, image, or quote to inspect what Proofpage keeps.
This is a labeled illustration, not a live library or a claim that a capture ran.
The existing typed terminal remains directly below it. The original botanical
SVG, paper folds, tape, and source-specific colors give the page a visual idea
that comes from collecting material, rather than another generic feature grid.

Typography now uses locally bundled [IBM Plex Sans](https://github.com/IBM/plex)
for headings and body copy, with JetBrains Mono reserved for commands and small
labels. IBM publishes Plex under the OFL and designed it for UI use. Its compact
forms suit the archive; removing the italic serif headlines makes room for the
notes to carry the personality. The font and its license add about 44 KiB.

## Research and implementation

- [Codrops Creative Hub](https://tympanus.net/codrops/hub/) collects experiments in ASCII, typography, dithering, and state-to-state animation. The useful direction here is a visual language derived from the product: text becomes a source record, then a receipt. The code and artwork in Proofpage are original; no demo code was copied.
- [Codrops' interactive stamp collection case study](https://tympanus.net/codrops/2026/06/09/building-an-interactive-digital-stamp-collection-with-shaders-postcards-and-playful-inspection/) demonstrates a browsable field of archival objects and focused inspection. The relevant lesson is to let an artifact be the interface. Proofpage uses accessible buttons and ordinary guide links rather than requiring drag gestures, a shader, or a custom cursor.
- [Motion animate](https://motion.dev/docs/animate) offers a small native HTML/SVG animation engine and a larger hybrid engine for sequencing and arbitrary values. It would be a good fit if the site grows into complex, coordinated transitions.
- [GSAP ScrollTrigger](https://gsap.com/docs/v3/Plugins/ScrollTrigger/) supports rich scroll-based scenes, synchronized updates, and responsive behavior. [gsap.matchMedia](https://gsap.com/docs/v3/GSAP/gsap.matchMedia/) documents reduced-motion handling. Those tools are useful for a longer interactive story; this page does not need pinned sections or a scroll runtime.
- [Web Animations API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Animations_API/Using_the_Web_Animations_API) handles the short stamp and entry effects directly. [Canvas animation](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial/Basic_animations) handles the character field, with requestAnimationFrame and a 24fps paint cap. Native APIs cover the current requirements without adding a library or a package/build step.

## Behavior and fallbacks

The terminal is an illustration, not an executable shell. Switching scenes changes the transcript, guide link, and receipt. The text alternative describes the workflow without announcing every typed character. Without JavaScript, the capture transcript, first screenshot, install links, and docs remain usable.

The animation loop cancels when paused, offscreen, or in a hidden tab. Canvas resolution is capped at 2x. Reduced motion starts with a full static transcript, static artwork, no entry transitions, and no autoplay video. Users can choose to play motion. Pause is saved independently from theme. Product video loads only on demand. View selection and platform selection use normal buttons with pressed state; no hover-only controls or custom cursor.

The forest and terminal have separate visibility checks, so an offscreen terminal
does not freeze a visible forest. Paths draw once; the leaves breathe slowly.
Pointer movement nudges the canopy by at most four pixels, and is disabled for
touch and reduced motion. Pause stops both scenes. Selecting a note also works
with a keyboard and updates one concise status message and a normal docs link.

Four additional screenshots show real onboarding, business context review,
assistant setup, and Settings from an isolated workspace with fictional content.
The page labels these as 0.5.1 previews while Google review is pending. Full-size
images remain ordinary links; no lightbox or mandatory gallery runtime is needed.
Screenshots are captured directly from the packaged engine's actual interface,
with no UI mockups or generated content layered over them.

Release links remain on the verified public version until a newer release is available. Google verification, privacy routes, original download instructions, creator credit, GitHub, and LinkedIn remain accessible.

## The paper airplane

A small, original folded-paper SVG launches across the hero on a curved path,
leaving a short dotted pencil trail. On a mouse-equipped screen it then follows
the pointer with a soft delay and banks into turns. It stays offset from the
pointer, never captures input, and never replaces the cursor. Coordinates are
used only in the page; no camera, tracking, or network request is involved.

Throw again is an ordinary keyboard-accessible button. The hero and terminal
share one saved pause preference. Reduced motion keeps the plane parked among
the notes and removes the throw control; touch screens get the initial throw and
a parked plane without pointer chasing. Hidden tabs stop work. The frame loop
also stops as soon as the plane settles, instead of running continuously at rest.
The plane and its trail add no library, image request, or build step.
