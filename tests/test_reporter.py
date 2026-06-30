import unittest
from codemorph.reporter import ReportGenerator
from codemorph.models import FileMigrationReport

class TestReportGenerator(unittest.TestCase):
    def setUp(self):
        self.reporter = ReportGenerator()

    def test_compile_report(self):
        file_reports = [
            FileMigrationReport(
                filepath="file_a.py",
                status="MIGRATED",
                intent_summary="Endpoint handler",
                test_pass_rate_before=0.5,
                test_pass_rate_after=1.0,
                semantic_diff_score=0.95,
                retries_needed=0
            ),
            FileMigrationReport(
                filepath="file_b.py",
                status="NEEDS_HUMAN_REVIEW",
                intent_summary="Database model",
                test_pass_rate_before=0.5,
                test_pass_rate_after=0.5,
                semantic_diff_score=None,
                retries_needed=3
            )
        ]

        report = self.reporter.compile_report(file_reports)
        
        self.assertEqual(report.total_files, 2)
        self.assertEqual(report.migrated_files, 1)
        self.assertEqual(report.needs_review_files, 1)
        # Average pass rates: before = 0.5, after = 0.75
        self.assertEqual(report.test_pass_rate_before, 0.5)
        self.assertEqual(report.test_pass_rate_after, 0.75)
        # Estimated review time: MIGRATED (3) + NEEDS_HUMAN_REVIEW (30) = 33 mins
        self.assertEqual(report.estimated_review_time_mins, 33)

    def test_markdown_generation(self):
        file_reports = [
            FileMigrationReport(
                filepath="file_a.py",
                status="MIGRATED",
                intent_summary="Simple addition helper",
                test_pass_rate_before=1.0,
                test_pass_rate_after=1.0,
                semantic_diff_score=0.98,
                retries_needed=0
            )
        ]
        report = self.reporter.compile_report(file_reports)
        md = self.reporter.generate_markdown(report)
        self.assertIn("**Total Files Scanned**: 1", md)
        self.assertIn("**Successfully Migrated**: 1 / 1", md)
        self.assertIn("file_a.py", md)
        self.assertIn("0.98", md)

if __name__ == "__main__":
    unittest.main()
