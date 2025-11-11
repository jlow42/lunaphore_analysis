import { BackgroundConfigResponse } from "./types";

const DEFAULT_API_BASE = "/api";

export interface ApiClientOptions {
  baseUrl?: string;
}

export class ApiClient {
  private readonly baseUrl: string;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = options.baseUrl ?? DEFAULT_API_BASE;
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      ...init,
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(`API request failed (${response.status}): ${detail}`);
    }
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }

  public getProjects() {
    return this.request("/projects");
  }

  public createIngest(payload: unknown) {
    return this.request("/ingest", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  public getIngestStatus(id: number) {
    return this.request(`/ingest/${id}`);
  }

  public getBackgroundConfig(): Promise<BackgroundConfigResponse> {
    return this.request("/preprocess/background/config");
  }

  public submitBackgroundJob(payload: unknown) {
    return this.request("/preprocess/background", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  public getBackgroundJob(jobId: number) {
    return this.request(`/preprocess/background/${jobId}`);
  }
}

export const apiClient = new ApiClient();
