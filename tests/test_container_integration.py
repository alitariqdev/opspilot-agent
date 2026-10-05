"""Integration tests for container log parsing with evidence retrieval."""

from pathlib import Path

import pytest

from src.opspilot.tools.container_log_parser import (
    parse_docker_log_file,
    parse_kubernetes_log_file,
)
from src.opspilot.tools.evidence_retriever import create_evidence_retriever


class TestContainerEvidenceRetrieval:
    """Tests for evidence retrieval with container logs."""

    def test_evidence_retrieval_with_docker_logs(self, tmp_path: Path):
        """Test that Docker logs are indexed and retrievable."""
        # Create Docker log file
        docker_log = tmp_path / "order-service.docker.log"
        docker_log.write_text(
            '{"log":"2024-03-15T14:20:16Z ERROR [order-service] Database connection pool exhausted\\n","stream":"stderr","time":"2024-03-15T14:20:16.123456789Z"}\n'
            '{"log":"2024-03-15T14:20:17Z ERROR [order-service] Failed to create order\\n","stream":"stderr","time":"2024-03-15T14:20:17.123456789Z"}\n'
            '{"log":"2024-03-15T14:26:09Z INFO [order-service] Order created successfully\\n","stream":"stdout","time":"2024-03-15T14:26:09.123456789Z"}\n'
        )

        # Parse logs
        entries = parse_docker_log_file(docker_log, "abc123", "order-service")

        # Create retriever
        retriever = create_evidence_retriever(entries, tmp_path)

        # Search for connection pool issues
        results = retriever.retrieve("database connection pool exhausted", top_k=5)

        assert len(results) > 0
        assert any("pool exhausted" in r.content.lower() for r in results)
        assert results[0].source_type == "log"
        assert results[0].metadata is not None
        assert results[0].metadata["log_source"] == "docker"
        assert results[0].metadata["container_name"] == "order-service"

    def test_evidence_retrieval_with_kubernetes_logs(self, tmp_path: Path):
        """Test that Kubernetes logs are indexed and retrievable."""
        # Create Kubernetes log file
        k8s_log = tmp_path / "postgres-pod_default_postgres.k8s.log"
        k8s_log.write_text(
            "2024-03-15T14:22:01.123456789Z stdout F 2024-03-15T14:22:01Z DEBUG [postgres] Connection pool: 20/20 connections active - pool exhausted\n"
            "2024-03-15T14:25:33.123456789Z stdout F 2024-03-15T14:25:33Z DEBUG [postgres] Long-running query detected: query_id=9847 duration=622s\n"
            "2024-03-15T14:26:06.123456789Z stdout F 2024-03-15T14:26:06Z DEBUG [postgres] Connection pool: 2/20 connections active\n"
        )

        # Parse logs
        entries = parse_kubernetes_log_file(
            k8s_log, "postgres-pod", "default", "postgres"
        )

        # Create retriever
        retriever = create_evidence_retriever(entries, tmp_path)

        # Search for long-running query
        results = retriever.retrieve("long running query", top_k=5)

        assert len(results) > 0
        assert any("long-running query" in r.content.lower() for r in results)
        assert results[0].metadata is not None
        assert results[0].metadata["log_source"] == "kubernetes"
        assert results[0].metadata["pod_name"] == "postgres-pod"
        assert results[0].metadata["namespace"] == "default"

    def test_evidence_retrieval_searches_container_metadata(self, tmp_path: Path):
        """Test that container metadata is searchable."""
        # Create Docker log
        docker_log = tmp_path / "api-gateway.docker.log"
        docker_log.write_text(
            '{"log":"2024-03-15T14:20:16Z INFO [api-gateway] Upstream service failed\\n","stream":"stdout","time":"2024-03-15T14:20:16.123456789Z"}\n'
        )

        entries = parse_docker_log_file(docker_log, "gw123", "api-gateway")
        retriever = create_evidence_retriever(entries, tmp_path)

        # Search by container name
        results = retriever.retrieve("container:api-gateway", top_k=5)

        assert len(results) > 0
        assert results[0].metadata["container_name"] == "api-gateway"

    def test_evidence_retrieval_with_mixed_container_logs(self, tmp_path: Path):
        """Test evidence retrieval with both Docker and Kubernetes logs."""
        # Create Docker log
        docker_log = tmp_path / "order-service.docker.log"
        docker_log.write_text(
            '{"log":"2024-03-15T14:20:16Z ERROR [order-service] Connection timeout\\n","stream":"stderr","time":"2024-03-15T14:20:16.123456789Z"}\n'
        )

        # Create Kubernetes log
        k8s_log = tmp_path / "postgres-pod.k8s.log"
        k8s_log.write_text(
            "2024-03-15T14:22:01.123456789Z stdout F 2024-03-15T14:22:01Z DEBUG [postgres] Pool exhausted\n"
        )

        # Parse both
        docker_entries = parse_docker_log_file(docker_log)
        k8s_entries = parse_kubernetes_log_file(k8s_log)
        all_entries = docker_entries + k8s_entries

        # Create retriever
        retriever = create_evidence_retriever(all_entries, tmp_path)

        # Search for connection issues
        results = retriever.retrieve("connection timeout pool", top_k=10)

        assert len(results) >= 2
        sources = {r.metadata["log_source"] for r in results}
        assert "docker" in sources
        assert "kubernetes" in sources

    def test_evidence_preserves_line_numbers_for_citations(self, tmp_path: Path):
        """Test that line numbers are preserved for evidence citations."""
        docker_log = tmp_path / "service.docker.log"
        docker_log.write_text(
            '{"log":"2024-03-15T14:20:16Z INFO [service] Line one\\n","stream":"stdout","time":"2024-03-15T14:20:16.123456789Z"}\n'
            '{"log":"2024-03-15T14:20:17Z ERROR [service] Critical error on line two\\n","stream":"stderr","time":"2024-03-15T14:20:17.123456789Z"}\n'
            '{"log":"2024-03-15T14:20:18Z INFO [service] Line three\\n","stream":"stdout","time":"2024-03-15T14:20:18.123456789Z"}\n'
        )

        entries = parse_docker_log_file(docker_log)
        retriever = create_evidence_retriever(entries, tmp_path)

        results = retriever.retrieve("critical error", top_k=1)

        assert len(results) == 1
        assert results[0].line_number == 2
        assert results[0].source_file == "service.docker.log"

    def test_evidence_chunks_have_stable_ids(self, tmp_path: Path):
        """Test that evidence IDs are stable across runs."""
        k8s_log = tmp_path / "pod.k8s.log"
        k8s_log.write_text(
            "2024-03-15T14:20:16.123456789Z stdout F 2024-03-15T14:20:16Z INFO [service] Message\n"
        )

        entries = parse_kubernetes_log_file(k8s_log)

        # Create retriever twice
        retriever1 = create_evidence_retriever(entries, tmp_path)
        retriever2 = create_evidence_retriever(entries, tmp_path)

        results1 = retriever1.retrieve("message", top_k=1)
        results2 = retriever2.retrieve("message", top_k=1)

        assert len(results1) == 1
        assert len(results2) == 1
        assert results1[0].evidence_id == results2[0].evidence_id


class TestContainerLogRealWorldScenarios:
    """Tests simulating real-world incident investigation scenarios."""

    def test_database_connection_pool_exhaustion_scenario(self, tmp_path: Path):
        """Test investigating connection pool exhaustion across multiple containers."""
        # Order service Docker logs
        order_log = tmp_path / "order-service.docker.log"
        order_log.write_text(
            '{"log":"2024-03-15T14:20:16Z WARN [order-service] Database connection timeout\\n","stream":"stderr","time":"2024-03-15T14:20:16.123456789Z"}\n'
            '{"log":"2024-03-15T14:20:16Z ERROR [order-service] Connection pool exhausted\\n","stream":"stderr","time":"2024-03-15T14:20:16.123456789Z"}\n'
        )

        # Postgres Kubernetes logs
        postgres_log = tmp_path / "postgres-pod_default_db.k8s.log"
        postgres_log.write_text(
            "2024-03-15T14:22:01.123456789Z stdout F 2024-03-15T14:22:01Z DEBUG [postgres] Connection pool: 20/20 active\n"
            "2024-03-15T14:25:33.123456789Z stdout F 2024-03-15T14:25:33Z DEBUG [postgres] Long-running query: 622s\n"
        )

        # Parse all logs
        order_entries = parse_docker_log_file(order_log)
        postgres_entries = parse_kubernetes_log_file(postgres_log)
        all_entries = order_entries + postgres_entries

        # Create retriever
        retriever = create_evidence_retriever(all_entries, tmp_path)

        # Investigate connection pool issues
        results = retriever.retrieve("connection pool exhausted timeout", top_k=10)

        assert len(results) >= 2
        # Should find evidence from both Docker and Kubernetes logs
        docker_evidence = [r for r in results if r.metadata["log_source"] == "docker"]
        k8s_evidence = [r for r in results if r.metadata["log_source"] == "kubernetes"]

        assert len(docker_evidence) > 0
        assert len(k8s_evidence) > 0

    def test_container_restart_investigation(self, tmp_path: Path):
        """Test investigating container restart events."""
        # Container logs showing restart
        container_log = tmp_path / "app-container.docker.log"
        container_log.write_text(
            '{"log":"2024-03-15T14:15:03Z INFO [app] Starting application version 2.4.1\\n","stream":"stdout","time":"2024-03-15T14:15:03.123456789Z"}\n'
            '{"log":"2024-03-15T14:23:47Z ERROR [app] Out of memory error\\n","stream":"stderr","time":"2024-03-15T14:23:47.123456789Z"}\n'
            '{"log":"2024-03-15T14:23:48Z ERROR [app] Application crashed\\n","stream":"stderr","time":"2024-03-15T14:23:48.123456789Z"}\n'
            '{"log":"2024-03-15T14:24:05Z INFO [app] Starting application version 2.4.1\\n","stream":"stdout","time":"2024-03-15T14:24:05.123456789Z"}\n'
        )

        entries = parse_docker_log_file(container_log)
        retriever = create_evidence_retriever(entries, tmp_path)

        # Search for crash and restart
        results = retriever.retrieve("out of memory crashed starting", top_k=10)

        assert len(results) >= 3
        # Verify we found the error and restart logs
        messages = [r.content.lower() for r in results]
        assert any("out of memory" in m for m in messages)
        assert any("crashed" in m for m in messages)
        assert any("starting application" in m for m in messages)
