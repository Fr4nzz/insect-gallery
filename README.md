# Insect AI Dataset Gallery

Interactive gallery for browsing and reviewing the training dataset used in the [Insect AI Classification](https://github.com/Fr4nzz/Insect_AI_Classification) pipeline for automated insect identification from Amazon Basin light-trap monitoring.

**Live:** [https://fr4nzz.github.io/insect-gallery/](https://fr4nzz.github.io/insect-gallery/)

## Features

- Browse 185K+ insect images from BioTrove (iNaturalist research-grade) and GBIF
- Filter by order, family, source, and curation status
- Review Gemini VLM curation decisions (keep/drop with specific reasons: larvae, habitat, quality, etc.)
- Grid and table views with lazy loading
- Full-resolution image modal with taxonomy details

## Dataset

- **BioTrove**: 185,827 research-grade iNaturalist images across 15 orders and 429 families
- **GBIF gap-fill**: 877 images for underrepresented families
- **Curation**: Gemini 3 Flash Preview grid-based quality assessment

## Development

```bash
npm install
npm run dev      # Dev server at http://localhost:5174/insect-gallery/
npm run build    # Production build to dist/
```

## Rebuilding dataset

```bash
python scripts/build_dataset.py
```

Reads manifests and curation results from the Insect_AI_Classification repo and outputs `public/data/dataset.json`.

## Part of

Franz Chandi's MSc thesis at USFQ — Tropical Ecology and Conservation. Automated classification pipeline for nocturnal insect monitoring at the Tiputini Biodiversity Station, Ecuadorian Amazon.
