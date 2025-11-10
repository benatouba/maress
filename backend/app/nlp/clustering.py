"""Coordinate clustering for study site extraction.

This module implements DBSCAN clustering that identifies the largest
geographic cluster and returns the best-ranked results from it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.neighbors import NearestNeighbors

from app.nlp.domain_models import GeoEntity
from app.nlp.nlp_logger import logger

if TYPE_CHECKING:
    pass


class CoordinateClusterer:
    """Clusters coordinates using DBSCAN and returns largest cluster.

    Identifies all geographic clusters but returns only entities from the
    largest cluster, which represents the primary study region.
    """

    def __init__(self, eps_km: float = 50.0, min_samples: int = 1) -> None:
        """Initialize clusterer.

        Args:
            eps_km: Maximum distance between points in same cluster (km)
            min_samples: Minimum points required to form a cluster
        """
        self.eps_km = eps_km
        self.min_samples = min_samples

    def cluster_entities(
        self,
        entities: list[GeoEntity],
    ) -> tuple[list[GeoEntity], dict[str, int]]:
        """Cluster entities with coordinates and return largest cluster.

        Args:
            entities: List of GeoEntity objects with coordinates

        Returns:
            Tuple of (entities from largest cluster, cluster size info)
        """
        # Filter entities with coordinates
        entities_with_coords = [e for e in entities if e.coordinates is not None]

        if len(entities_with_coords) <= 1:
            # No clustering needed
            return entities, {}

        # Extract coordinates for clustering
        coords = [e.coordinates for e in entities_with_coords]
        X = np.radians(np.array(coords))

        # Adaptive eps based on data distribution
        if len(coords) >= 3:
            self.eps_km = self._estimate_optimal_eps(coords)

        earth_radius_km = 6371.0088
        eps_rad = self.eps_km / earth_radius_km

        # Perform clustering
        clustering = DBSCAN(
            eps=eps_rad,
            min_samples=self.min_samples,
            metric="haversine",
        ).fit(X)

        labels = clustering.labels_

        # Group by cluster and assign labels
        clustered: dict[int, list[tuple[GeoEntity, int]]] = {}
        for entity, label in zip(entities_with_coords, labels, strict=False):
            if label not in clustered:
                clustered[label] = []
            clustered[label].append((entity, label))

        logger.info(f"DBSCAN found {len(clustered)} clusters with eps={self.eps_km:.1f} km")

        # Sort clusters by size (largest first)
        sorted_cluster_labels = sorted(
            clustered.keys(),
            key=lambda k: len(clustered[k]),
            reverse=True,
        )

        # Log all clusters for debugging
        cluster_info = {}
        for cluster_label in sorted_cluster_labels:
            cluster = clustered[cluster_label]
            cluster_info[f"cluster_{cluster_label}"] = len(cluster)
            logger.info(f"Cluster {cluster_label}: {len(cluster)} entities")

        # Keep only the largest cluster
        if sorted_cluster_labels:
            largest_cluster_label = sorted_cluster_labels[0]
            largest_cluster = clustered[largest_cluster_label]

            logger.info(
                f"Keeping largest cluster ({largest_cluster_label}) with "
                f"{len(largest_cluster)} entities out of {len(entities_with_coords)} total"
            )

            # Extract entities from largest cluster only
            largest_cluster_entities = [entity for entity, label in largest_cluster]

            # Add entities without coordinates (they should still be considered)
            entities_without_coords = [e for e in entities if e.coordinates is None]
            result_entities = largest_cluster_entities + entities_without_coords

            return result_entities, cluster_info
        else:
            # No clusters found, return original entities
            logger.warning("No clusters found, returning all entities")
            return entities, cluster_info

    def _estimate_optimal_eps(self, coordinates: list[tuple[float, float]]) -> float:
        """Estimate optimal eps using k-distance plot heuristic.

        Args:
            coordinates: List of (lat, lon) tuples

        Returns:
            Estimated optimal eps in kilometers
        """
        if len(coordinates) < 3:
            return self.eps_km

        X = np.radians(np.array(coordinates))

        k = min(3, len(coordinates) - 1)
        nbrs = NearestNeighbors(n_neighbors=k, metric="haversine").fit(X)
        distances, _ = nbrs.kneighbors(X)

        # Use the elbow of sorted k-distances
        k_distances = np.sort(distances[:, -1])
        median_distance = np.median(k_distances)

        earth_radius_km = 6371.0088
        estimated_eps = median_distance * earth_radius_km * 1.5

        # Clamp to reasonable range
        estimated_eps = max(10.0, min(200.0, estimated_eps))

        logger.debug(f"Estimated optimal eps: {estimated_eps:.1f} km")
        return estimated_eps


def add_cluster_labels_to_entities(
    entities: list[GeoEntity],
    cluster_info: dict[str, int],
) -> list[tuple[GeoEntity, int | None]]:
    """Add cluster labels to entities based on proximity.

    Since GeoEntity is immutable, returns list of (entity, cluster_label) tuples.

    Args:
        entities: List of entities
        cluster_info: Cluster size information

    Returns:
        List of (entity, cluster_label) tuples
    """
    # Simple implementation: entities are already in cluster order
    # from cluster_entities(), so we can assign labels based on position

    result: list[tuple[GeoEntity, int | None]] = []
    cluster_idx = 0
    current_cluster_size = 0
    cluster_keys = list(cluster_info.keys())

    for entity in entities:
        if entity.coordinates is None:
            result.append((entity, None))
            continue

        # Assign cluster label
        if cluster_idx < len(cluster_keys):
            cluster_key = cluster_keys[cluster_idx]
            cluster_label = int(cluster_key.split("_")[1])
            result.append((entity, cluster_label))

            current_cluster_size += 1
            if current_cluster_size >= cluster_info[cluster_key]:
                cluster_idx += 1
                current_cluster_size = 0
        else:
            result.append((entity, None))

    return result
