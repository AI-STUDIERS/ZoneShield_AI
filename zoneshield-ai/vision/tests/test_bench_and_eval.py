"""Unit tests for Benchmarking and Evaluation modules."""

from pathlib import Path

from benchmarks.run import run_microbenchmarks, run_pipeline_benchmark
from eval.run import evaluate_scenarios


def test_microbenchmarks_run():
    results = run_microbenchmarks(reps=2, width=160, height=120)
    assert "resize_downscale" in results
    assert "gaussian_blur" in results
    assert "adaptive_threshold" in results
    assert "find_contours" in results
    for op, data in results.items():
        assert "mean_ms" in data
        assert data["mean_ms"] >= 0


def test_pipeline_benchmark_run():
    pipe_results = run_pipeline_benchmark(reps=3)
    assert "mean_ms" in pipe_results
    assert "throughput_fps" in pipe_results
    assert pipe_results["throughput_fps"] > 0


def test_evaluation_scenarios_run():
    metrics = evaluate_scenarios(agent_mode="mock", num_frames=10)
    assert "precision" in metrics
    assert "recall" in metrics
    assert "f1_score" in metrics
    assert "trajectory_mae_mm" in metrics
    assert "confusion_matrix" in metrics
    assert metrics["precision"] >= 0.0
