import datetime as dt
import tempfile
import unittest
from pathlib import Path

from scripts.generate_profile_assets import (
    aggregate_languages,
    bucket_public_events,
    render_assets,
)


class GenerateProfileAssetsTests(unittest.TestCase):
    def test_aggregate_languages_orders_and_percentages(self) -> None:
        languages = aggregate_languages(
            [
                {"Go": 600, "TypeScript": 200},
                {"Go": 400, "Dart": 300},
            ]
        )

        self.assertEqual([item[0] for item in languages[:3]], ["Go", "Dart", "TypeScript"])
        self.assertAlmostEqual(languages[0][2], 66.6666, places=2)

    def test_bucket_public_events_limits_to_recent_window(self) -> None:
        today = dt.date(2026, 9, 17)
        counts, total_events, touched_repos = bucket_public_events(
            [
                {"created_at": "2026-09-17T12:00:00Z", "repo": {"name": "fira6007/fira6007"}},
                {"created_at": "2026-09-16T12:00:00Z", "repo": {"name": "fira6007/demo"}},
                {"created_at": "2026-08-01T12:00:00Z", "repo": {"name": "ignored/repo"}},
            ],
            today=today,
            days=14,
        )

        self.assertEqual(total_events, 2)
        self.assertEqual(touched_repos, 2)
        self.assertEqual(counts[-1], 1)
        self.assertEqual(counts[-2], 1)

    def test_render_assets_preserves_existing_card_on_fetch_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output_dir = Path(tempdir)
            existing = output_dir / "github-overview.svg"
            existing.write_text("keep-me", encoding="utf-8")

            def failing_fetch(_: str, __: str | None) -> None:
                raise RuntimeError("network down")

            warnings = render_assets(
                "fira6007",
                output_dir,
                token=None,
                today=dt.date(2026, 9, 17),
                fetch_json=failing_fetch,
            )

            self.assertIn("github-overview.svg", warnings)
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep-me")
            self.assertTrue((output_dir / "github-languages.svg").exists())
            self.assertTrue((output_dir / "github-activity.svg").exists())

    def test_render_assets_handles_empty_public_data(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output_dir = Path(tempdir)

            def fake_fetch(url: str, _: str | None):
                if url == "https://api.github.com/users/fira6007":
                    return {"public_repos": 0, "followers": 0, "following": 0}
                if "repos?type=owner&sort=updated" in url:
                    return []
                if "events/public" in url:
                    return []
                raise AssertionError(f"Unexpected URL: {url}")

            warnings = render_assets(
                "fira6007",
                output_dir,
                token=None,
                today=dt.date(2026, 9, 17),
                fetch_json=fake_fetch,
            )

            self.assertEqual(warnings, {})
            self.assertIn(
                "Language data is not available yet.",
                (output_dir / "github-languages.svg").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "This is not a complete contribution graph.",
                (output_dir / "github-activity.svg").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
