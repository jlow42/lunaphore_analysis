import React, { useEffect, useMemo, useState } from "react";

type VivViewerComponent = React.ComponentType<any>;

type LoadedLayer = {
  loader: any;
  name: string;
};

export interface VivPreviewProps {
  correctedUrl?: string | null;
  backgroundUrl?: string | null;
}

export function VivPreview({ correctedUrl, backgroundUrl }: VivPreviewProps) {
  const [VivViewerComponent, setVivViewerComponent] = useState<VivViewerComponent | null>(null);
  const [layers, setLayers] = useState<LoadedLayer[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!correctedUrl && !backgroundUrl) {
        setLayers([]);
        return;
      }
      try {
        const [{ VivViewer }, loaders] = await Promise.all([
          import("@vivjs/react"),
          import("@vivjs/loaders"),
        ]);
        if (cancelled) return;
        setVivViewerComponent(() => VivViewer as VivViewerComponent);
        const nextLayers: LoadedLayer[] = [];
        if (backgroundUrl) {
          const background = (await loaders.loadOmeZarr({ url: backgroundUrl, path: "background" })) as any;
          nextLayers.push({ loader: background, name: "Background" });
        }
        if (correctedUrl) {
          const corrected = (await loaders.loadOmeZarr({ url: correctedUrl, path: "corrected" })) as any;
          nextLayers.push({ loader: corrected, name: "Corrected" });
        }
        if (!cancelled) {
          setLayers(nextLayers);
        }
      } catch (err) {
        if (!cancelled) {
          setError((err as Error).message);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [correctedUrl, backgroundUrl]);

  const viewStates = useMemo(
    () => [
      { id: "background", target: [0, 0, 0], zoom: 0 },
      { id: "corrected", target: [0, 0, 0], zoom: 0 },
    ],
    [],
  );

  if (error) {
    return <div className="viv-error">Viv preview unavailable: {error}</div>;
  }

  if (!correctedUrl && !backgroundUrl) {
    return <div>No background correction results yet.</div>;
  }

  if (!VivViewerComponent || !layers.length) {
    return <div>Loading Viv viewer…</div>;
  }

  return (
    <VivViewerComponent
      loader={layers.map((layer) => layer.loader)}
      layerProps={layers.map((layer) => ({ name: layer.name }))}
      views={[
        { id: "background", x: 0, y: 0, width: 0.5, height: 1 },
        { id: "corrected", x: 0.5, y: 0, width: 0.5, height: 1 },
      ]}
      viewStates={viewStates}
      viewerWidth={900}
      viewerHeight={420}
    />
  );
}
