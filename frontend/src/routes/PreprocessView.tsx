import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import {
  BackgroundConfigResponse,
  BackgroundMethodConfig,
  BackgroundPreprocessRequest,
  BackgroundPreprocessResponse,
  BackgroundPreprocessStatus,
  IngestStatusModel,
} from "../api/types";
import { apiClient } from "../api/client";
import { usePollingQuery } from "../hooks/usePollingQuery";
import { VivPreview } from "../components/VivPreview";

function toNumber(value: string) {
  const parsed = Number(value);
  return Number.isNaN(parsed) ? undefined : parsed;
}

export function PreprocessView() {
  const { slug = "" } = useParams();
  const [ingestId, setIngestId] = useState<number | null>(null);
  const [selectedMethod, setSelectedMethod] = useState<string | null>(null);
  const [parameters, setParameters] = useState<Record<string, unknown>>({});
  const [channels, setChannels] = useState<string>("");
  const [jobId, setJobId] = useState<number | null>(null);

  const configQuery = useQuery<BackgroundConfigResponse>({
    queryKey: ["background-config"],
    queryFn: () => apiClient.getBackgroundConfig(),
  });

  const ingestStatus = usePollingQuery<IngestStatusModel | undefined>(
    ["ingest-metadata", ingestId],
    () => apiClient.getIngestStatus(ingestId ?? 0),
    {
      enabled: ingestId != null,
      refetchInterval: 10_000,
    },
  );

  const submitBackground = useMutation({
    mutationFn: (payload: BackgroundPreprocessRequest) =>
      apiClient.submitBackgroundJob(payload) as Promise<BackgroundPreprocessResponse>,
    onSuccess: (response) => {
      setJobId(response.job_id);
    },
  });

  const backgroundStatus = usePollingQuery<BackgroundPreprocessStatus | undefined>(
    ["background-status", jobId],
    () => apiClient.getBackgroundJob(jobId ?? 0),
    {
      enabled: jobId != null,
      refetchInterval: (data) =>
        data?.status && ["completed", "failed"].includes(data.status) ? false : 2500,
    },
  );

  const selectedMethodConfig: BackgroundMethodConfig | undefined = useMemo(() => {
    return configQuery.data?.methods.find((method) => method.name === selectedMethod);
  }, [configQuery.data, selectedMethod]);

  useEffect(() => {
    if (!selectedMethodConfig) {
      setParameters({});
      return;
    }
    const defaults: Record<string, unknown> = {};
    selectedMethodConfig.parameters.forEach((parameter) => {
      if (parameter.default !== undefined) {
        defaults[parameter.name] = parameter.default as unknown;
      }
    });
    setParameters(defaults);
  }, [selectedMethodConfig]);

  const onParameterChange = (name: string, value: string) => {
    setParameters((prev) => ({ ...prev, [name]: toNumber(value) ?? value }));
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!ingestId || !selectedMethod) {
      alert("Select an ingest record and method.");
      return;
    }
    const payload: BackgroundPreprocessRequest = {
      project_slug: slug,
      ingest_record_id: ingestId,
      method: selectedMethod,
      output_name: `${selectedMethod}-${Date.now()}`,
      parameters,
      channels: channels
        ? channels
            .split(",")
            .map((value) => Number(value.trim()))
            .filter((value) => !Number.isNaN(value))
        : undefined,
    };
    submitBackground.mutate(payload);
  };

  const qcMetrics = backgroundStatus.data?.qc_metrics as Record<string, unknown> | undefined;

  return (
    <div className="preprocess-view">
      <h2>Background correction</h2>
      <form onSubmit={onSubmit} className="preprocess-form">
        <label>
          Ingest record ID
          <input
            type="number"
            value={ingestId ?? ""}
            onChange={(event) => setIngestId(event.target.value ? Number(event.target.value) : null)}
          />
        </label>
        <label>
          Method
          <select
            value={selectedMethod ?? ""}
            onChange={(event) => setSelectedMethod(event.target.value || null)}
          >
            <option value="">Select method</option>
            {configQuery.data?.methods.map((method) => (
              <option key={method.name} value={method.name}>
                {method.label}
              </option>
            ))}
          </select>
        </label>
        {selectedMethodConfig && (
          <fieldset>
            <legend>Parameters</legend>
            {selectedMethodConfig.parameters.map((parameter) => (
              <label key={parameter.name}>
                {parameter.label}
                <input
                  type="number"
                  defaultValue={parameter.default as number | undefined}
                  onChange={(event) => onParameterChange(parameter.name, event.target.value)}
                  min={parameter.minimum}
                  max={parameter.maximum}
                />
                {parameter.description && <small>{parameter.description}</small>}
              </label>
            ))}
          </fieldset>
        )}
        <label>
          Channels (comma separated indices)
          <input value={channels} onChange={(event) => setChannels(event.target.value)} />
        </label>
        <button type="submit" disabled={submitBackground.isPending}>
          {submitBackground.isPending ? "Submitting…" : "Run background correction"}
        </button>
      </form>
      {ingestStatus.data?.channel_metadata && (
        <section>
          <h3>Channel metadata</h3>
          <pre>{JSON.stringify(ingestStatus.data.channel_metadata, null, 2)}</pre>
        </section>
      )}
      {backgroundStatus.data && (
        <section className="background-status">
          <h3>Background job</h3>
          <p>Status: {backgroundStatus.data.status}</p>
          <p>Progress: {(backgroundStatus.data.progress * 100).toFixed(0)}%</p>
          {backgroundStatus.data.error_message && (
            <p className="error">{backgroundStatus.data.error_message}</p>
          )}
          {qcMetrics && (
            <div className="qc-metrics">
              <h4>QC metrics</h4>
              <table>
                <thead>
                  <tr>
                    <th>Statistic</th>
                    <th>Raw</th>
                    <th>Background</th>
                    <th>Corrected</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    "mean",
                    "std",
                    "min",
                    "max",
                  ].map((metric) => (
                    <tr key={metric}>
                      <td>{metric}</td>
                      <td>{(qcMetrics.raw as Record<string, number>)?.[metric]}</td>
                      <td>{(qcMetrics.background as Record<string, number>)?.[metric]}</td>
                      <td>{(qcMetrics.corrected as Record<string, number>)?.[metric]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {Array.isArray((qcMetrics.per_channel as unknown) ?? []) && (
                <details>
                  <summary>Per-channel metrics</summary>
                  <pre>{JSON.stringify(qcMetrics.per_channel, null, 2)}</pre>
                </details>
              )}
            </div>
          )}
          <VivPreview
            backgroundUrl={backgroundStatus.data.result_zarr_path || undefined}
            correctedUrl={backgroundStatus.data.result_zarr_path || undefined}
          />
        </section>
      )}
    </div>
  );
}
