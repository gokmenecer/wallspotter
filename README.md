# WallSpotter

Source of [www.wallspotter.com](https://www.wallspotter.com). The site is generated from a simple list and published automatically by GitHub Pages.

## Adding a new wallpaper

1. Open `data/wallpapers.csv` on GitHub and click the pencil (Edit) icon.
2. Add a new line **right under the header line**:

   ```
   mobile-wallpaper-103,2026-10-20,mobile,https://i.pinimg.com/736x/xx/xx/xx/xxxxxxxx.jpg
   ```

   | Column | What to write |
   |---|---|
   | `slug` | Page address, e.g. `mobile-wallpaper-103` → wallspotter.com/mobile-wallpaper-103/ (must be unique) |
   | `date` | `YYYY-MM-DD` |
   | `category` | `mobile` or `desktop` |
   | `image` | The Pinterest image link (right-click the image on Pinterest → *Copy image address*) |

   Optional extra columns: `title` (defaults to "Mobile Wallpaper") and `pin` (link to the Pinterest pin, shows a "View on Pinterest" button). To use them, add them to the header line too.
3. Click **Commit changes**. The site updates itself in about a minute.

## Other files

- `config.json` — site name, Google Analytics IDs and AdSense ID (both empty = none), Web3Forms contact key, social links, old-address redirects
- `pages/` — About, Contact, Privacy, Terms and other text pages
- `static/` — logo, CSS and other files copied as-is
- `build.py` — the generator (run `python3 build.py` to build into `_site/`)
