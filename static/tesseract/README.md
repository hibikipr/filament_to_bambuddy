# Locally-bundled Tesseract.js assets

This app is meant to run on a home network, sometimes fully offline. It
previously loaded `tesseract.js` itself from `cdn.jsdelivr.net` on first use
of the photo-OCR button, and Tesseract.js in turn defaults to fetching its
worker script, WASM core, and language data from that same CDN — so OCR
silently failed offline and made an un-opted external request otherwise.
These files exist so it works fully offline instead.

| File | Source | Version | Why this variant |
| --- | --- | --- | --- |
| `tesseract.min.js` | `tesseract.js` (UMD browser bundle, `dist/tesseract.min.js`) | 7.0.0 | Exposes `window.Tesseract` (`createWorker`, `OEM`, ...) — same global API the old CDN script provided. |
| `worker.min.js` | `tesseract.js`, `dist/worker.min.js` | 7.0.0 | The Web Worker script. |
| `tesseract-core-lstm.wasm(.js)` | `tesseract.js-core` | 7.0.0 | LSTM-only build — this app never uses the legacy OCR engine (`OEM.LSTM_ONLY`), so the plain (non-SIMD) LSTM-only core is the smallest correct choice. `tesseract.js-core` also ships SIMD/relaxed-SIMD variants for a speed bump on supporting browsers, intentionally not bundled here to keep this small. |
| `eng.traineddata.gz` | `@tesseract.js-data/eng`, the `4.0.0_best_int` variant | 1.0.0 | Quantized ("best_int") English model — matches what Tesseract.js's own CDN fallback picks for `lstmOnly` mode. ~3 MB vs. ~11 MB for the full-precision `4.0.0` model, no meaningful accuracy loss for this app's use (short printed label text). |

## Committed, not generated

Unlike bambuddy (a Vite/npm project that regenerates these from
`node_modules` at `postinstall` time), this app has no JS build step or
package manager — it's a single Flask app serving static assets directly.
So these are committed here as binary files rather than generated.

To refresh them (e.g. bumping to a newer tesseract.js release), pull the
same version from a project that has it as an npm dependency (bambuddy does)
and copy:

- `node_modules/tesseract.js/dist/tesseract.min.js`
- `node_modules/tesseract.js/dist/worker.min.js`
- `node_modules/tesseract.js-core/tesseract-core-lstm.wasm.js`
- `node_modules/tesseract.js-core/tesseract-core-lstm.wasm`
- `node_modules/@tesseract.js-data/eng/4.0.0_best_int/eng.traineddata.gz`

Keep the three package versions in sync with whatever bambuddy pins, so both
apps behave identically.
