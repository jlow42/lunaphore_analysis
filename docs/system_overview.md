# SPARC System Overview

This document summarizes the architecture, data model, and functional requirements for the Spatial Proteomics Analysis & Review Console (SPARC).

## Project Vision

SPARC delivers an end-to-end analysis environment for Lunaphore COMET™ multiplex immunofluorescence data. The platform ingests high-volume OME-TIFF inputs, performs tiled image corrections and segmentation, computes single-cell feature matrices, integrates batch-aware analytics, and surfaces interactive spatial visualizations for review and annotation. The system must scale to multi-slide datasets (≥50 GB per slide, ≥1e6 cells) while ensuring reproducible, configuration-driven workflows.

## High-Level Architecture

- **Backend (Python 3.11, FastAPI)**
  - Async REST API with background task orchestration (Celery/RQ + Redis/PostgreSQL job store).
  - Modular service layers for ingestion, preprocessing, segmentation, feature extraction, normalization, clustering, spatial analytics, and exports.
  - Event-stream/WebSocket endpoints for long-running job progress updates.
- **Data and Compute Stack**
  - OME-TIFF ingestion via `bioformats`, `aicsimageio`, or `tifffile` with optional OME-Zarr/NGFF conversion for chunked access.
  - Distributed array processing with `dask`, `zarr`, and `xarray`; lazy pyramid loading for large imagery.
  - Single-cell analytics powered by `anndata`, `scanpy`, `squidpy`, and `spatialdata` (scverse ecosystem).
  - Segmentation engines primarily using InstanSeg (PyTorch) with plugin adapters for Cellpose and StarDist.
  - Optional GPU acceleration (RAPIDS/cuML/cuGraph) with CPU fallbacks.
- **Frontend (React + TypeScript)**
  - Dashboard integrating project management, pipeline configuration, analytics views, and spatial tile viewers.
  - Visualization stack combining Viv/deck.gl (or OpenSeadragon) for multi-channel imagery with overlays, and Plotly-based analytical charts.
- **Storage Layout**
  - Project workspaces containing imagery (OME-TIFF/Zarr), segmentation masks, AnnData (`.h5ad`) feature matrices, and SpatialData linking geometry to imagery.
  - Versioned YAML configs, run logs, input checksums, and code hashes to guarantee reproducibility.

## Data Model Conventions

- **AnnData (`adata`)**
  - `adata.X`: per-cell marker expression matrix (normalized view).
  - `adata.raw.X`: raw intensities post background subtraction and illumination correction.
  - `adata.layers`: named layers for processed matrices (e.g., `bg_subtracted`, `illum_corrected`, `normalized:<method>`, `batch_corrected:<method>`).
  - `adata.obs`: cell metadata including morphology metrics (area, perimeter, eccentricity, solidity), nuclei/cytoplasm areas, centroid coordinates (`x`, `y` in microns), provenance (`slide_id`, `batch_id`, `roi_id`), and QC flags (`qc_*`).
  - `adata.obs["clust:<key>"]`: multiple clustering assignments (Leiden, HDBSCAN, etc.).
  - Manual annotations stored in `adata.obs["cluster_label:<key>"]` and `adata.obs["cell_type"]`.
  - `adata.obsm`: dimensionality reductions and spatial embeddings (e.g., `X_pca`, `X_umap:<key>`, `X_tsne:<key>`, `X_phate:<key>`, `spatial`).
  - `adata.obsp`: adjacency/graph matrices (kNN, radius, spatial weights).
  - `adata.uns`: pipeline configs, marker panels, color maps, QC summaries, and subcluster lineage metadata.
- **SpatialData**
  - Links imagery, segmentation geometries (polygons), and coordinate transforms.
- **Segmentation Masks**
  - Instance-labeled 2D arrays stored as TIFF/Zarr plus GeoJSON polygons to accelerate overlay rendering.

## Pipeline Stages

1. **Ingestion & Metadata**
   - Read COMET OME-TIFF files, extract channel metadata, and optionally convert to OME-Zarr with configurable chunking/compression.
   - Channel mapping UI loads panel CSVs for marker-channel alignment and supports manual relabeling.
   - Sample/ROI selection UI chooses slides, ROIs, and channel subsets.

2. **Preprocessing**
   - Illumination correction methods: BaSiC (CPU/GPU), polynomial/spline models, morphological top-hat, rolling-ball filters.
   - Background subtraction via percentile-based, wavelet, or local adaptive methods.
   - Autofluorescence handling through linear regression/unmixing against autofluorescence channels; support spectral unmixing when metadata available.
   - Store corrected outputs as lazy Dask arrays; capture QC metrics (background level, SNR, saturation) and provide raw vs corrected previews.

3. **Segmentation**
   - InstanSeg as the default engine with configurable model variants, tiling, thresholds, and optional GPU execution.
   - Plugin APIs for Cellpose, StarDist, or custom mask uploads.
   - Outputs include instance masks, contours, centroids, and per-tile quality scores; overlays viewable in the tile viewer.

4. **Feature Extraction**
   - Intensity summaries per marker (mean/median, robust z-scores, positivity percentages) with nuclear/cytoplasmic splits.
   - Morphological descriptors (area, perimeter, roundness, eccentricity, solidity) and texture features (Haralick/Gabor).
   - Spatial provenance features and threshold provenance records.

5. **Batch Handling**
   - Image-level harmonization (percentile normalization, histogram matching, control-based scaling).
   - Cell-level integration (ComBat, MNN, Harmony, BBKNN) with preserved pre-batch layers and audit logs.
   - Visual QC comparing pre/post distributions and embedding separations.

6. **Normalization & Transformation**
   - Methods include total intensity scaling, quantile normalization, per-marker z-score, arcsinh (configurable cofactor), and log1p.
   - Each result stored in `adata.layers["normalized:<method>"]` with parameters captured in `adata.uns`.

7. **Dimensionality Reduction**
   - PCA, UMAP, t-SNE, PHATE, force-directed layouts, and optional diffusion maps with tunable hyperparameters and multi-key storage.

8. **Clustering & Subclustering**
   - Graph-based (Leiden, Louvain, Phenograph, Spectral), centroid-based (K-Means, MiniBatch), density-based (HDBSCAN, OPTICS), model-based (GMM, DPGMM), and hierarchical (Agglomerative, BIRCH) methods.
   - Clustering Manager stores unique keys (e.g., `clust:leiden_r1.0_k15`), supports subclustering with recorded lineage trees, and integrates differential expression/marker discovery utilities.

9. **Annotations**
   - Editable mappings from clusters to labels stored as `cluster_label:<key>`.
   - Cell-type annotation via signature scoring, probabilistic classifiers (multinomial logistic, naïve Bayes), and threshold-based gating with audit logs.

10. **Spatial Analytics**
    - High-performance radius and graph queries (kNN, radius-R) with Dask chunking and optional GPU.
    - Metrics: neighborhood enrichment, permutation tests, Moran’s I, Geary’s C, Ripley’s K/L, pair correlation functions, spatial cross-correlation, density/proportion maps, and patch-level statistics.
    - Caching strategies for repeated radius queries.

11. **Visualization**
    - Embedding viewers (UMAP/t-SNE/PHATE) with lasso selection and color-by options.
    - Heatmaps, violin/ridge plots, stacked bar charts for cluster compositions.
    - Whole-slide tile viewer with channel toggles, contrast sliders, segmentation overlays, and interactive hover tooltips.
    - Patch explorer for generating/exporting region summaries.
    - Comparative views evaluating clustering agreements (ARI/NMI, confusion matrices).

12. **Exports & Reproducibility**
    - Export AnnData/SpatialData bundles, segmentation masks, per-cell/per-patch tables, static plot images, and UI state snapshots.
    - Versioned configs with recorded package versions, random seeds, input checksums, and code hashes. Re-runs produce new immutable records.

## API Surface (FastAPI)

Key async endpoints returning job IDs:
- `POST /projects` (create project) and `GET /projects/{id}` (status).
- Pipeline stage endpoints: `/ingest`, `/preprocess/background`, `/segment`, `/features/extract`, `/batch/harmonize`, `/batch/integrate`, `/normalize`, `/reduce`, `/cluster`, `/subcluster`, `/annotate/cluster`, `/annotate/celltype`, `/spatial/graph`, `/spatial/metrics`.
- Tile server: `GET /tiles/{slide}/{z}/{x}/{y}`.
- Artifact download: `GET /download/{artifact}`.

## Frontend Experience

- **Project Home**: dataset list, run history, logs, configs.
- **Ingest Wizard**: file selection, channel mapping, ROI selection.
- **Preprocess Panel**: method selection, parameter tuning, raw vs corrected previews.
- **Segmentation Panel**: engine configuration, live tile previews, overlay toggles, run controls.
- **Explore Workspace**: embedding viewer, heatmaps, clustering manager, annotation editor, batch QA diagnostics.
- **Spatial Viewer**: multi-channel imagery, segmentation overlays, hover tooltips, patch explorer with exports.
- **Exports Center**: download artifacts with version tracking.

## Performance Targets

- Stream tiled operations with peak RAM < 1/3 of slide size (≥50 GB inputs).
- Segment ≥1e6 cells/slide with GPU acceleration when available; CPU fallback via chunked inference.
- Spatial graphs scaling to ≥2e6 nodes using chunked radius queries and optional GPU acceleration.

## Testing & Acceptance Criteria

- Unit/integration tests covering ingestion, preprocessing, segmentation outputs, normalization/batch corrections, clustering coexistence, and spatial metrics.
- End-to-end acceptance flow verifying ingestion through export reproducibility, including performance expectations for previews and analytics responsiveness.

## Deliverables

- Structured repository with backend, frontend, CLI, docker, configs, docs, data examples, notebooks, and scripts.
- Dockerized services for backend API, workers, and frontend UI.
- Synthetic datasets and panel/signature examples.
- Comprehensive API documentation (OpenAPI), user docs, and a quickstart notebook.
- Optional enhancements: registration refinements, compositional analyses, interactive gating UI, and a Napari plugin.
