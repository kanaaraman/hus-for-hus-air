# Hus för hus

Every building in Stockholm, coloured by the year it was built, with live air quality, noise and water levels.

**Live:** https://kanaaraman.github.io/hus-for-hus-air/

The whole app is one HTML file (`index.html`) with no build step and no server of its own. It runs in the browser and talks directly to open data services.

## What it does

- **Building map:** about 164,000 buildings in Stockholm, shown in 3D by default and coloured by construction year. Drag the timeline (or press ▶) to watch the city grow. Click a building for its year, address, the shops or museums inside it, and its Wikipedia summary and photo when one exists.
- **Search:** finds streets, addresses, building names and what's inside. Accents and word order don't matter ("sveavagen 12" works). Addresses that aren't in the building data are looked up with OpenStreetMap's Nominatim and marked 📍.
- **Air & noise:** hourly NO₂ and PM10 from the Norrlandsgatan 21 street station, with charts, WHO guideline comparisons and a multi-year trend. Also shows noise levels from two meters on Sveavägen and Norrlandsgatan.
- **Water:** sea levels and warnings for Stockholm from SMHI.
- **Ask about the air (optional):** questions about the air data are answered by a language model running on *your own computer* through [Ollama](https://ollama.com). Nothing is sent to an AI service. See [Using the AI questions](#using-the-ai-questions).
- **Map options:** map styles (light, classic, bright, night), raised terrain, 3D on/off, only buildings with a photo, Swedish/English.

## Building data

The building data is prebuilt and served from this repository, so the map loads in a few seconds without depending on the Overpass API.

- `data/index.json` lists 25 area pieces, `data/<x>_<y>.json`, about 8 MB in total as downloaded.
- The app loads the piece in view first, then the rest. It saves everything in the browser (IndexedDB), so later visits are instant.
- If a piece fails to load, the app falls back to downloading those buildings from Overpass. **Map options → Download fresh data** also re-downloads everything from Overpass.

### How the data is updated

The [Update building data](.github/workflows/update-buildings.yml) workflow runs **on GitHub's servers on the 1st of every month**:

1. It downloads the [BBBike OpenStreetMap extract of Stockholm](https://download.bbbike.org/osm/bbbike/Stockholm/).
2. It runs [`tools/build_buildings.py`](tools/build_buildings.py). This script turns buildings, addresses and named places into the same format the app builds in the browser, then adds photos and years from Wikidata.
3. It commits `data/` if anything changed, and GitHub Pages republishes the site.

To update right away, open **Actions → Update building data → Run workflow**. You don't need to run anything on your own computer. Each update adds about 8 MB to the repository history.

### About the build years

Years come from OpenStreetMap tags (`start_date`, `building:start_date`, `construction_date`, …) and from Wikidata's "inception" date. Only about 1% of Stockholm's buildings have one today. Everything else is shown in grey as "unknown". You can fix years and addresses in OpenStreetMap: each building card has a link for that, and the next monthly update picks the changes up.

## Using the AI questions

1. Install [Ollama](https://ollama.com) and pull a model, for example `ollama pull qwen2.5:7b`.
2. Allow this site to talk to Ollama. On Windows:
   ```
   setx OLLAMA_ORIGINS "https://kanaaraman.github.io,http://localhost,http://127.0.0.1"
   ```
   Then restart Ollama.
3. Open **Air & noise**, choose the model under *Ollama settings* and ask a question.

Visitors who don't run Ollama simply don't get this feature; the rest of the app works without it. Some browsers ask for permission before a website can reach `localhost`, and some ad blockers block it.

## Repository layout

| Path | What it is |
| --- | --- |
| `index.html` | The whole app: HTML, CSS and JavaScript |
| `data/` | Prebuilt building data (generated; don't edit by hand) |
| `tools/build_buildings.py` | Builds `data/` from an OpenStreetMap `.pbf` extract |
| `.github/workflows/update-buildings.yml` | Monthly rebuild of `data/` on GitHub |
| `.nojekyll` | Tells GitHub Pages to publish the files as they are |

GitHub Pages publishes the `main` branch, root folder.

## Data sources and licences

- **Buildings, addresses, places, geocoding:** © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, [ODbL](https://opendatacommons.org/licenses/odbl/). Extract via [BBBike](https://download.bbbike.org/osm/); search via [Nominatim](https://nominatim.org).
- **Years and photos:** [Wikidata](https://www.wikidata.org) (CC0) and [Wikimedia Commons](https://commons.wikimedia.org) (photo licences vary per image). Summaries from [Wikipedia](https://www.wikipedia.org) (CC BY-SA).
- **Base map:** [OpenFreeMap](https://openfreemap.org), using OpenMapTiles and OpenStreetMap data.
- **Terrain:** AWS Open Data terrain tiles (Mapzen).
- **Air quality:** [SLB-analys](https://www.slb.nu) open data, station Norrlandsgatan 21.
- **Noise:** EnviroSuite meters on Sveavägen and Norrlandsgatan.
- **Water levels and warnings:** [SMHI open data](https://www.smhi.se/data) (CC BY 4.0). Not an official warning service; always follow SMHI.
- **Map library:** [MapLibre GL JS](https://maplibre.org) 4.7.1.

## Note on API keys

The noise feature calls the EnviroSuite API with two API keys that are written into `index.html`. Because this repository and site are public, anyone can read and use those keys. Removing them from the current file won't hide them, because they stay in the git history. To revoke them, rotate the keys with EnviroSuite and update `index.html`.
