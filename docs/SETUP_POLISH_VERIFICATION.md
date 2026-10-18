# Setup and automation update

- Settings now leads with browser pairing and links to AI access, scheduling and training. Signing keys and timestamp options remain available under Evidence integrity.
- Pairing shows separate port/code fields with a copy-code button. Notification controls describe their actual on/off action.
- Companion source 0.3.1 separates page capture, public web files and local originals. Its Chrome permissions and behavior are unchanged. Store review still contains 0.3.0.
- MCP adds validated source registration and schedule/pause tools. Both the web API and MCP use shared scheduling validation; the app/server must remain running.
- Agent access has copyable collection, cited-research and training prompts. Client guidance distinguishes local MCP clients from ChatGPT/Claude web connectors.

Validation: 124 Python tests passed, including new schedule boundaries, pause, duplicate source registration, public-destination enforcement and existing hosted-scope/training export tests. Companion JavaScript tests, Python compilation, JavaScript syntax checks and diff whitespace checks passed. In the browser: light/dark Settings, code creation, agent navigation, advanced controls and chain check passed with no console errors. Companion styling was inspected in a static preview without Chrome APIs; this is not a live extension transfer test.

The user reported completing a Chrome save, but neither the earlier isolated test workspace nor the running desktop app's default data workspace contained a saved record when checked. End-to-end confirmation of that transfer remains unresolved.

These are source changes, not a new signed installer or an update to the pending Chrome Store package. Native audio/video extraction, multimodal trainer formats, and a ChatGPT-ready remote MCP connector remain outside the implemented capabilities.


## MCP and skill follow-up

127 tests pass. New subprocess acceptance starts the generated source MCP configuration from an unrelated working directory with spaces in the workspace path. It verifies initialize, tool discovery, source listing, no response to notifications, and a structured error for invalid schedule input. A session-authenticated HTTP diagnostic runs the real helper; unauthenticated requests fail. Skill validation passes and every referenced tool exists. The built wheel contains the skill and portable entry point; desktop packaging includes the skill directory.

Browser acceptance: the Test MCP connection button returned 29 tools and the correct one-source fixture workspace. Download SKILL.md produced bytes identical to the packaged file. Scheduling a daily run persisted, reopening showed that choice, and pausing restored manual collection. No new installer or client configuration was installed by these tests.
