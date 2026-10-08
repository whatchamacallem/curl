# Notes

## URL components

- `debug`: query key, value `1`, that unfreezes the settings so the settings
  view can apply a setting.
- `file`: hash key, heat map view only, that names the source file to open.
- `function`: hash key, heat map view only, that names the function to open and
  excludes `file` and `line`.
- `line`: hash key, heat map view only, that names the line within `file` to
  scroll to.
- `localProfilePath`: hash key, flame graph view only, that is speedscope's own
  key naming the profile to load.
- `screenshot`: query key whose value is shown as a label on the page.
- `screenshot-menu`: query key, a menu entry number, that opens or focuses
- `screenshot-mode`: query key, `1` dark or `0` light, that sets the mode a
  screenshot is shot in. that entry after each menu render.
- `setting`: hash key, settings view only, that names the setting scrolled to
  the top.
- `setting-val`: hash key, settings view only, that carries the base64 JSON of
  the new value for `setting`, applied on load.
- `test`: hash key that names the test shown, `all` being the merged test.
- `view`: hash key, one of `callers`, `heat-map`, `flame-graph` or `settings`,
  that names the page framed, required whenever `test` is present.
