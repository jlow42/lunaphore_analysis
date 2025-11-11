import { FormEvent, useEffect, useMemo, useState } from "react";
import Papa from "papaparse";
import { useParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { IngestResponse, IngestStatusModel } from "../api/types";
import { usePollingQuery } from "../hooks/usePollingQuery";

type PanelRow = {
  channel: string;
  target: string;
};

type RoiSelection = {
  id: string;
  name: string;
  include: boolean;
  previewUrl?: string;
};

function parsePanelCsv(file: File, onComplete: (rows: PanelRow[]) => void) {
  Papa.parse(file, {
    header: true,
    skipEmptyLines: true,
    complete: (result) => {
      const rows: PanelRow[] = [];
      for (const raw of result.data as Papa.ParseResult<PanelRow>["data"]) {
        const channel = (raw.channel ?? "").toString();
        const target = (raw.target ?? "").toString();
        if (channel) {
          rows.push({ channel, target });
        }
      }
      onComplete(rows);
    },
  });
}

export function IngestFlowView() {
  const { slug = "" } = useParams();
  const [runName, setRunName] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [panelRows, setPanelRows] = useState<PanelRow[]>([]);
  const [channelMapping, setChannelMapping] = useState<Record<string, string>>({});
  const [rois, setRois] = useState<RoiSelection[]>([]);
  const [ingestId, setIngestId] = useState<number | null>(null);

  const ingestMutation = useMutation({
    mutationFn: (payload: unknown) => apiClient.createIngest(payload),
    onSuccess: (response: IngestResponse) => {
      setIngestId(response.ingest_record_id);
    },
  });

  const ingestStatus = usePollingQuery<IngestStatusModel | undefined>(
    ["ingest-status", ingestId],
    () => apiClient.getIngestStatus(ingestId ?? 0),
    {
      enabled: ingestId != null,
      refetchInterval: (data) =>
        data?.status && ["completed", "failed"].includes(data.status) ? false : 2500,
    },
  );

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!imageFile) {
      alert("Please select an imagery file before submitting.");
      return;
    }
    const metadata = {
      channel_mapping: channelMapping,
      rois: rois.map(({ id, name, include }) => ({ id, name, include })),
    };
    ingestMutation.mutate({
      project_slug: slug,
      run_name: runName || imageFile.name,
      image_path: imageFile.name,
      convert_to_zarr: true,
      panel_csv_path: panelRows.length ? "panel.csv" : undefined,
      metadata,
    });
  };

  const onPanelChange = (file: File | null) => {
    if (!file) {
      setPanelRows([]);
      setChannelMapping({});
      return;
    }
    parsePanelCsv(file, (rows) => {
      setPanelRows(rows);
      const mapping: Record<string, string> = {};
      rows.forEach((row) => {
        mapping[row.channel] = row.target;
      });
      setChannelMapping(mapping);
    });
  };

  const onChannelTargetChange = (channel: string, target: string) => {
    setChannelMapping((prev) => ({ ...prev, [channel]: target }));
  };

  const addRoi = (file: File, name: string) => {
    const id = `${Date.now()}-${file.name}`;
    const previewUrl = URL.createObjectURL(file);
    setRois((prev) => [...prev, { id, name, include: true, previewUrl }]);
  };

  const toggleRoi = (id: string) => {
    setRois((prev) =>
      prev.map((roi) =>
        roi.id === id
          ? {
              ...roi,
              include: !roi.include,
            }
          : roi,
      ),
    );
  };

  const mappedChannels = useMemo(() => Object.entries(channelMapping), [channelMapping]);

  useEffect(() => {
    return () => {
      rois.forEach((roi) => {
        if (roi.previewUrl) {
          URL.revokeObjectURL(roi.previewUrl);
        }
      });
    };
  }, [rois]);

  return (
    <div className="ingest-flow">
      <h2>Imagery ingestion</h2>
      <form onSubmit={onSubmit} className="ingest-form">
        <label>
          Run name
          <input value={runName} onChange={(event) => setRunName(event.target.value)} />
        </label>
        <label>
          Select imagery file
          <input
            type="file"
            accept=".tif,.tiff,.ome.tiff"
            onChange={(event) => setImageFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <label>
          Panel CSV
          <input
            type="file"
            accept=".csv"
            onChange={(event) => onPanelChange(event.target.files?.[0] ?? null)}
          />
        </label>
        {!!panelRows.length && (
          <table className="panel-table">
            <thead>
              <tr>
                <th>Channel</th>
                <th>Target</th>
              </tr>
            </thead>
            <tbody>
              {panelRows.map((row) => (
                <tr key={row.channel}>
                  <td>{row.channel}</td>
                  <td>
                    <input
                      value={channelMapping[row.channel] ?? ""}
                      onChange={(event) => onChannelTargetChange(row.channel, event.target.value)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <fieldset>
          <legend>Regions of interest</legend>
          <label>
            ROI preview image
            <input
              type="file"
              accept="image/*"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (!file) return;
                const name = file.name.replace(/\.[^.]+$/, "");
                addRoi(file, name);
                event.target.value = "";
              }}
            />
          </label>
          {!rois.length && <p>No ROIs added yet. Upload preview images to define ROIs.</p>}
          <ul className="roi-list">
            {rois.map((roi) => (
              <li key={roi.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={roi.include}
                    onChange={() => toggleRoi(roi.id)}
                  />
                  {roi.name}
                </label>
                {roi.previewUrl && <img src={roi.previewUrl} alt={roi.name} width={120} />}
              </li>
            ))}
          </ul>
        </fieldset>
        <button type="submit" disabled={!imageFile || ingestMutation.isPending}>
          {ingestMutation.isPending ? "Submitting…" : "Submit ingest"}
        </button>
      </form>
      {mappedChannels.length > 0 && (
        <section>
          <h3>Channel mapping summary</h3>
          <ul>
            {mappedChannels.map(([channel, target]) => (
              <li key={channel}>
                {channel} → {target || "(unassigned)"}
              </li>
            ))}
          </ul>
        </section>
      )}
      {ingestStatus.data && (
        <section className="ingest-status">
          <h3>Ingest progress</h3>
          <p>Status: {ingestStatus.data.status}</p>
          {ingestStatus.data.error_message && (
            <p className="error">{ingestStatus.data.error_message}</p>
          )}
          {ingestStatus.data.channel_metadata && (
            <details>
              <summary>Detected channels</summary>
              <pre>{JSON.stringify(ingestStatus.data.channel_metadata, null, 2)}</pre>
            </details>
          )}
        </section>
      )}
    </div>
  );
}
