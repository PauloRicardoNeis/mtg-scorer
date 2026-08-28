package dev.mtgscorer.api.catalog;

public record CardScores(
        double staple,
        double buildaroundSignal,
        double evidence,
        double distinctivenessDelta,
        double stapleFeatureCoverage,
        double buildaroundFeatureCoverage) {}
