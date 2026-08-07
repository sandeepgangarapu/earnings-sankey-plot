# Result View, Export, and Sharing Design

## Goal

Make it unambiguous whether a control changes the visible result or downloads a file. Users should be able to inspect the chart, SVG source, or normalized JSON; download the relevant artifact; copy useful content; and share the result through common social channels.

## Interaction model

The result toolbar will contain a segmented `Chart / SVG / JSON` mode switcher. These controls only change the visible result and never trigger a download.

Each mode will show a compact action row immediately above its content:

- **Chart:** `Copy image`, `Download`, and `Share`. `Download` opens a disclosure with explicit `Download PNG`, `Download SVG`, and `Download HTML` actions.
- **SVG:** `Download SVG` and `Copy SVG code` above a readable, scrollable source preview.
- **JSON:** `Download JSON` and `Copy JSON` above a readable, scrollable normalized-data preview.

The Chart mode remains the default whenever a result is generated or the sample is opened. The active mode is visually distinct and represented with `aria-selected` semantics. Mode content uses a tab-panel relationship so keyboard and assistive-technology users can understand the control.

## Sharing

`Share` opens a small anchored menu containing:

- Native Share, when the Web Share API is available.
- LinkedIn.
- X.
- Facebook.

Social-network links share the current page URL. X also receives concise prepared text containing the company, ticker, fiscal year, and period; LinkedIn and Facebook derive their preview from the shared page because their composer URLs do not accept custom post text. The controls do not claim to attach the generated chart because those services do not accept arbitrary local SVG data through share URLs.

Native Share will attempt to include a generated SVG file when the browser supports file sharing; otherwise it shares the title, prepared text, and current page URL. The menu closes after an action, when clicking outside it, or when pressing Escape.

## Copy and feedback

`Copy image` renders the chart to a two-times-resolution PNG and writes it as `image/png` through the asynchronous Clipboard API. This makes the chart directly pasteable into messaging, email, documents, and presentation software. When image clipboard access is unavailable, the status message points users to `Download PNG` rather than claiming success.

Source-copy actions write the complete active representation to the clipboard: raw SVG markup in SVG mode and pretty-printed normalized JSON in JSON mode. `Copy SVG code` is deliberately labeled as code so it cannot be mistaken for copying a pasteable chart image.

After a successful copy, the action label temporarily changes to `Copied` and an accessible live region announces the result. If the Clipboard API is unavailable or rejects the request, a legacy selection-based fallback is attempted. If both methods fail, an inline status message explains that copying was unavailable; the interface must not report false success.

## Components and data flow

The server API and result payload remain unchanged. The browser stores the result and active mode in its existing client state.

Small client-side helpers will provide:

- Mode selection and tab/panel state synchronization.
- SVG, JSON, and standalone HTML serialization.
- SVG-to-PNG rasterization at two-times resolution.
- Filename generation and file download.
- Clipboard copying with fallback and status feedback.
- Share metadata and social-share URL generation.
- Share-menu open/close behavior.

Source previews use `textContent`, not HTML interpolation, so generated SVG and JSON appear as inert text. The existing rendered chart continues to use the server-produced SVG markup.

## Visual design

The controls will extend the app's current light, compact visual language rather than introduce a modal or side drawer. The mode switcher will read as navigation, while download/copy/share actions will use explicit verb-first labels. Code previews use a restrained monospace treatment, horizontal scrolling, and sufficient contrast. On narrow screens, metadata and controls wrap without hiding actions or forcing the whole page wider than the viewport.

## Error and compatibility behavior

- Generating a new result resets the view to Chart and closes the share menu.
- Download actions are inert when no result exists and are only exposed with a visible result.
- Pop-up blockers may prevent a social-share window; the underlying share link remains a standard anchor so users can open it normally.
- Native Share and clipboard capability checks happen at action time.
- PNG generation failures surface in the existing action-status region and never leave temporary object URLs allocated.
- A cancelled native-share prompt is not shown as an error.

## Testing

Automated tests will verify:

- The HTML contains the three correctly labeled mode controls and explicit verb-first actions.
- Mode switching updates the active tab, visible panel, and relevant action set without invoking download behavior.
- Copy helpers select the correct SVG or JSON representation and expose success/failure feedback.
- Share URL builders encode the expected page URL and prepared text for LinkedIn, X, and Facebook.
- Generating or loading a result resets the active mode to Chart.
- Existing loading, empty, error, and result hidden-state behavior remains correct.

Browser verification will cover desktop and mobile layouts, keyboard mode switching, share-menu dismissal, code-preview scrolling, and visible copy feedback.

## Out of scope

- Uploading or hosting generated SVG files for social previews.
- Server-side share pages or permanent result URLs.
- Adding an HTML source-preview mode.
- Changing the API response or financial normalization logic.
