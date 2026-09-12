# Magic effects repair

Enhanced includes corrections to scripted effects and their coordinates:

- Frame sprites now receive their model, position, render settings and script
  callback before submission. The Xash renderer rejected the previous submission
  because it had no model. Erratic Lightning's hand sprites use this path.
- Dynamic lights validate all required parameters and read optional flags only
  when present. Ordinary six-parameter spell lights previously read past the end
  of the argument list; optional entity/dark flags were skipped.
- Script getters and number/vector formatters now retain valid return storage.
  They previously returned pointers into destroyed temporary or local strings.
  An actual test cast reached the client but attempted to play its lightning
  sound at `(0,0,0)`. The affected formatters produce both the spell's network
  endpoints and its final client-side position, width and related values.

The spell sprites, models and WAV files were checked against the supplied game
assets. No replacement artwork or sound files were needed. Stable remains the
existing rollback version.

`ms_debug_effects 1` enables targeted diagnostics in the Enhanced client/server
console: effect send/receipt, script activation, sampled rendering calls, and
resolved positional sound calls. It defaults to `0` and does not change the
network protocol. Use `ms_debug_effects 0` to disable it.

The native regression harness extracts the production light and frame-entity
branches and checks them with bounds-checked arguments and the engine's model
requirement. It covers missing/optional light arguments, disabled dynamic lights,
sprite initialization, callback order, missing models and permanent entities.
Independent mutations restoring each original bug cause the harness to fail.

The separate native lifetime regression compiles the real string implementation,
formatter functions and getter dispatch. It verifies that returned text survives
stack reuse, successive formatter calls, nested getters and another thread.
Restoring either original lifetime bug fails the regression.

See DEBUG-VALIDATION.md for runtime test evidence and remaining limits.
