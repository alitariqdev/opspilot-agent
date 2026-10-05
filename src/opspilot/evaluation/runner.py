"""Command-line benchmark runner."""

import sys
from pathlib import Path

from src.opspilot.config import get_config
from src.opspilot.evaluation.executor import run_benchmark
from src.opspilot.evaluation.reporter import (
    generate_json_report,
    generate_markdown_report,
    print_console_summary,
)


def get_project_root() -> Path:
    """Get project root directory.

    Returns:
        Path to project root (where data/ directory is located)
    """
    # This file is in src/opspilot/evaluation/runner.py
    # Project root is 4 levels up
    return Path(__file__).parent.parent.parent.parent


def main() -> int:
    """Run evaluation benchmark.

    Returns:
        Exit code: 0 for success, 1 for execution failure
    """
    project_root = get_project_root()
    data_dir = project_root / "data"
    cases_file = data_dir / "evaluation" / "benchmark_cases.json"
    output_dir = project_root / "evaluation_results"

    # Check if benchmark cases exist
    if not cases_file.exists():
        print(f"Error: Benchmark cases file not found: {cases_file}")
        return 1

    # Load configuration
    config = get_config()

    # Determine mode: demo by default, live if configured
    mode = "demo"
    live_available = False

    if config.opspilot_mode == "live":
        try:
            config.validate_live_mode()
            live_available = True
        except ValueError:
            # Live mode not properly configured
            pass

    print(f"Running benchmark in {mode.upper()} mode...")
    print(f"Cases file: {cases_file}")
    print(f"Data directory: {data_dir}")
    print()

    try:
        # Run demo mode benchmark
        demo_report = run_benchmark(cases_file, data_dir, mode="demo", config=config)

        # Print console summary
        print_console_summary(demo_report)

        # Generate reports
        demo_json_path = output_dir / "benchmark_demo.json"
        demo_md_path = output_dir / "benchmark_demo.md"

        generate_json_report(demo_report, demo_json_path)
        generate_markdown_report(demo_report, demo_md_path)

        print(f"Demo results saved:")
        print(f"  JSON: {demo_json_path}")
        print(f"  Markdown: {demo_md_path}")
        print()

        # Run live mode benchmark if available
        if live_available:
            print("Running live mode comparison...")
            print()

            live_report = run_benchmark(
                cases_file, data_dir, mode="live", config=config
            )

            # Print console summary
            print_console_summary(live_report)

            # Generate reports
            live_json_path = output_dir / "benchmark_live.json"
            live_md_path = output_dir / "benchmark_live.md"

            generate_json_report(live_report, live_json_path)
            generate_markdown_report(live_report, live_md_path)

            print(f"Live results saved:")
            print(f"  JSON: {live_json_path}")
            print(f"  Markdown: {live_md_path}")
            print()
        else:
            print("Live mode comparison: SKIPPED (API key not configured)")
            print("  To enable live mode:")
            print("    1. Set OPSPILOT_MODE=live in .env")
            print("    2. Set OPENAI_API_KEY in .env")
            print()

        print("Benchmark completed successfully!")
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        error_type = type(e).__name__
        print(f"Error: Benchmark execution failed ({error_type})")
        return 1


if __name__ == "__main__":
    sys.exit(main())
