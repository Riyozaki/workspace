# Pelican on a Bike 🚲🦩

Vector illustration: **пеликан на велосипеде** — a white pelican doing a wheelie on a teal bike,
one wing on the handlebar, the other thrown out for balance, webbed orange feet on the pedals.

| file | what it is |
| --- | --- |
| `pelican_bike.svg` | the illustration itself — pure SVG, ~20 KB, no raster data, scales losslessly |
| `pelican_bike.png` | 1920×1440 raster preview |
| `preview.png` | 1200 px preview |
| `gen_pelican.py` | the Python generator that builds the SVG |

## Viewing

Open `pelican_bike.svg` in any browser — it is self-contained (no external fonts or images,
only gradients defined inside the file). It also renders in `<img src="pelican_bike.svg">`.

## Regenerating / editing

```bash
python3 gen_pelican.py     # rewrites pelican_bike.svg next to the script
```

`gen_pelican.py` is a small drawing DSL: the scene is described in upright coordinates
(`RH`, `FH`, `BB`, `SEAT`, `BAR` …) and the whole rider + bike group is rotated around the
rear hub by `TILT` degrees to get the wheelie.

Helpers you can reuse:

* `wheel(cx, cy)` — spoked wheel (tyre, rim, hub)
* `band(path, w)` / `taper(points, widths)` — outlined tubes for the neck, wings and legs
* `blade(bx, by, ang, len, half_width)` / `feather_set(...)` — single feather / overlapping feathers
* `foot(x, y, rot, scale)` — webbed pelican foot
* `bird_wing(base, ctrl, tip, w0, w1, n)` — tapered wing with scalloped feather tips

Palette: sky `#9fd8ff`, grass `#74c168`, frame `#1f7a8c`, bill `#f9a12c`, legs `#f08b2e`.
