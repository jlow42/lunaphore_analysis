export interface ProjectLayout {
  root: string;
  imagery: string;
  masks: string;
  h5ad: string;
  spatialdata: string;
  configs: string;
  logs: string;
  snapshots: string;
}

export interface ProjectResponse {
  slug: string;
  title?: string | null;
  description?: string | null;
  root_path: string;
  created_at: string;
  layout: ProjectLayout;
}

export interface RunSnapshotModel {
  id: number;
  run_name: string;
  manifest_path: string;
  git_hash?: string | null;
  dependencies: Array<Record<string, string>>;
  inputs: Array<Record<string, string>>;
  created_at: string;
}

export interface IngestResponse {
  task_id: string;
  ingest_record_id: number;
  project: ProjectResponse;
  snapshot: RunSnapshotModel;
}

export interface IngestRequestPayload {
  project_slug: string;
  run_name: string;
  image_path: string;
  convert_to_zarr?: boolean;
  panel_csv_path?: string | null;
  metadata?: Record<string, unknown>;
}

export interface IngestStatusModel {
  id: number;
  status: string;
  source_path: string;
  panel_csv_path?: string | null;
  zarr_path?: string | null;
  channel_metadata?: Array<Record<string, unknown>> | null;
  scale_metadata?: Record<string, unknown> | null;
  panel_mapping?: Record<string, string> | null;
  request_metadata?: Record<string, unknown> | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BackgroundMethodParameter {
  name: string;
  label: string;
  type: string;
  default?: unknown;
  minimum?: number;
  maximum?: number;
  choices?: unknown[] | null;
  description?: string | null;
}

export interface BackgroundMethodConfig {
  name: string;
  label: string;
  description?: string | null;
  parameters: BackgroundMethodParameter[];
}

export interface BackgroundConfigResponse {
  methods: BackgroundMethodConfig[];
}

export interface BackgroundPreprocessRequest {
  project_slug: string;
  ingest_record_id: number;
  method: string;
  output_name: string;
  parameters: Record<string, unknown>;
  channels?: number[] | null;
}

export interface BackgroundPreprocessResponse {
  task_id: string;
  job_id: number;
  status: string;
}

export interface BackgroundPreprocessStatus {
  id: number;
  method: string;
  output_name: string;
  status: string;
  progress: number;
  result_zarr_path?: string | null;
  qc_metrics?: Record<string, unknown> | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}
