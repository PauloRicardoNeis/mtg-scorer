package dev.mtgscorer.api.catalog;

public record CatalogSnapshot(
        String datasetSnapshotId,
        String featurePipelineVersion,
        String scoreModelVersion,
        String scoreConfigHash,
        String publishedAt) {}
