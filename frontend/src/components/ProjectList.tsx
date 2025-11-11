import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiClient } from "../api/client";
import { ProjectResponse } from "../api/types";

export function ProjectList() {
  const { data, isLoading, error } = useQuery<ProjectResponse[]>({
    queryKey: ["projects"],
    queryFn: () => apiClient.getProjects(),
  });

  if (isLoading) {
    return <div>Loading projects…</div>;
  }

  if (error) {
    return <div className="error">Failed to load projects: {(error as Error).message}</div>;
  }

  if (!data?.length) {
    return <div>No projects available yet.</div>;
  }

  return (
    <div className="project-list">
      <h2>Projects</h2>
      <ul>
        {data.map((project) => (
          <li key={project.slug}>
            <div className="project-card">
              <div>
                <h3>{project.title ?? project.slug}</h3>
                {project.description && <p>{project.description}</p>}
                <small>Created {new Date(project.created_at).toLocaleString()}</small>
              </div>
              <div className="project-actions">
                <Link to={`/projects/${project.slug}/ingest`}>Ingest Imagery</Link>
                <Link to={`/projects/${project.slug}/preprocess`}>Background Correction</Link>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
