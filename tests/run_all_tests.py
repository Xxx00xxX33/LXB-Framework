#!/usr/bin/env python3
"""
LXB-Link Test Suite Runner - Binary First Architecture

Runs all test suites and generates comprehensive test reports.

Directory structure:
- tests/unit/           - Unit tests for protocol layer (Binary First)
- tests/integration/    - Integration tests (future: Mock Device + Client)
- tests/legacy/         - Legacy tests from previous versions
- tests/logs/           - Test output logs

Usage:
    python tests/run_all_tests.py              # Run all tests
    python tests/run_all_tests.py unit         # Run only unit tests
    python tests/run_all_tests.py legacy       # Run only legacy tests
"""

import sys
import unittest
import logging
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Configure root logger
log_dir = Path(__file__).parent / 'logs'
log_dir.mkdir(exist_ok=True)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = log_dir / f'test_run_{timestamp}.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='w'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def print_banner(text):
    """Print formatted banner"""
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80 + "\n")


def run_unit_tests():
    """Run all unit tests for Binary First architecture"""
    print_banner("Unit Tests - Binary First Architecture")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Discover unit tests
    unit_dir = Path(__file__).parent / 'unit'
    unit_tests = loader.discover(str(unit_dir), pattern='test_*.py')

    suite.addTests(unit_tests)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


def run_legacy_tests():
    """Run legacy tests from previous versions"""
    print_banner("Legacy Tests - Previous Versions")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Discover legacy tests
    legacy_dir = Path(__file__).parent / 'legacy'
    if legacy_dir.exists():
        legacy_tests = loader.discover(str(legacy_dir), pattern='test_*.py')
        suite.addTests(legacy_tests)
    else:
        logger.warning("No legacy tests directory found")
        return None

    if suite.countTestCases() == 0:
        logger.warning("No legacy tests found")
        return None

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


def run_integration_tests():
    """Run integration tests (Mock Device + Client)"""
    print_banner("Integration Tests - End-to-End")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Discover integration tests
    integration_dir = Path(__file__).parent / 'integration'
    if integration_dir.exists():
        integration_tests = loader.discover(str(integration_dir), pattern='test_*.py')
        suite.addTests(integration_tests)
    else:
        logger.warning("No integration tests directory found")
        return None

    if suite.countTestCases() == 0:
        logger.info("No integration tests found (coming soon)")
        return None

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result


def print_summary(results):
    """Print test execution summary"""
    print_banner("Test Execution Summary")

    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0

    for name, result in results.items():
        if result is None:
            continue

        tests_run = result.testsRun
        failures = len(result.failures)
        errors = len(result.errors)
        skipped = len(result.skipped)

        total_tests += tests_run
        total_failures += failures
        total_errors += errors
        total_skipped += skipped

        status = "[PASS]" if result.wasSuccessful() else "[FAIL]"
        print(f"{name}:")
        print(f"  Tests run: {tests_run}")
        print(f"  Failures: {failures}")
        print(f"  Errors: {errors}")
        print(f"  Skipped: {skipped}")
        print(f"  Status: {status}\n")

    print("-" * 80)
    print(f"TOTAL TESTS: {total_tests}")
    print(f"TOTAL FAILURES: {total_failures}")
    print(f"TOTAL ERRORS: {total_errors}")
    print(f"TOTAL SKIPPED: {total_skipped}")

    overall_success = (total_failures == 0 and total_errors == 0)
    overall_status = "[PASS] ALL TESTS PASSED" if overall_success else "[FAIL] SOME TESTS FAILED"
    print(f"\n{overall_status}")
    print(f"\nDetailed logs saved to: {log_file}")

    return overall_success


def main():
    """Main test runner entry point"""
    print_banner("LXB-Link Test Suite - Binary First Architecture")

    logger.info(f"Test run started at {datetime.now()}")
    logger.info(f"Log file: {log_file}")

    # Parse command line arguments
    test_type = sys.argv[1] if len(sys.argv) > 1 else 'all'

    results = {}

    if test_type in ('all', 'unit'):
        logger.info("Running unit tests...")
        results['Unit Tests'] = run_unit_tests()

    if test_type in ('all', 'integration'):
        logger.info("Running integration tests...")
        results['Integration Tests'] = run_integration_tests()

    if test_type in ('all', 'legacy'):
        logger.info("Running legacy tests...")
        results['Legacy Tests'] = run_legacy_tests()

    # Print summary
    success = print_summary(results)

    logger.info(f"Test run completed at {datetime.now()}")

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
