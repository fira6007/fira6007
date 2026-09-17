import datetime as dt
import tempfile
import unittest
from pathlib import Path

from scripts.generate_profile_assets import (
    EVENT_PAGE_LIMIT,
    LANGUAGE_REPO_LIMIT,
    aggregate_languages,
    bucket_public_events,
    fetch_all_pages,
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
                {"created_at": "not-a-date", "repo": {"name": "ignored/bad-event"}},
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
                fetcher=failing_fetch,
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
                fetcher=fake_fetch,
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

    def test_render_assets_preserves_existing_languages_when_repo_fetch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output_dir = Path(tempdir)
            languages_card = output_dir / "github-languages.svg"
            languages_card.write_text("keep-languages", encoding="utf-8")

            def partial_fetch(url: str, _: str | None):
                if url == "https://api.github.com/users/fira6007":
                    return {"public_repos": 7, "followers": 0, "following": 0}
                if "repos?type=owner&sort=updated" in url:
                    raise RuntimeError("repo api unavailable")
                if "events/public" in url:
                    return []
                raise AssertionError(f"Unexpected URL: {url}")

            warnings = render_assets(
                "fira6007",
                output_dir,
                token=None,
                today=dt.date(2026, 9, 17),
                fetcher=partial_fetch,
            )

            self.assertIn("github-languages.svg", warnings)
            self.assertEqual(languages_card.read_text(encoding="utf-8"), "keep-languages")

    def test_render_assets_limits_language_fetches(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            output_dir = Path(tempdir)
            language_calls = 0
            language_urls = []

            def fake_fetch(url: str, _: str | None):
                nonlocal language_calls
                if url == "https://api.github.com/users/fira6007":
                    return {"public_repos": LANGUAGE_REPO_LIMIT + 5, "followers": 1, "following": 2}
                if "repos?type=owner&sort=updated" in url:
                    return [
                        {"name": f"repo-{index}", "stargazers_count": 0, "pushed_at": "2026-09-17T00:00:00Z", "languages_url": f"https://example.test/lang/{index}"}
                        for index in range(LANGUAGE_REPO_LIMIT + 5)
                    ]
                if url.startswith("https://example.test/lang/"):
                    language_calls += 1
                    language_urls.append(url)
                    return {"Go": 10}
                if "events/public" in url:
                    return []
                raise AssertionError(f"Unexpected URL: {url}")

            warnings = render_assets(
                "fira6007",
                output_dir,
                token=None,
                today=dt.date(2026, 9, 17),
                fetcher=fake_fetch,
            )

            self.assertEqual(warnings, {})
            self.assertEqual(language_calls, LANGUAGE_REPO_LIMIT)
            self.assertEqual(
                language_urls,
                [f"https://example.test/lang/{index}" for index in range(LANGUAGE_REPO_LIMIT)],
            )

    def test_fetch_all_pages_respects_max_pages(self) -> None:
        requested_urls = []

        def fake_fetch(url: str, _: str | None):
            requested_urls.append(url)
            return [{"page": len(requested_urls)}] * 100

        rows = fetch_all_pages(
            "https://api.github.com/users/fira6007/events/public",
            fetch_json=fake_fetch,
            max_pages=EVENT_PAGE_LIMIT,
        )

        self.assertEqual(len(requested_urls), EVENT_PAGE_LIMIT)
        self.assertEqual(len(rows), EVENT_PAGE_LIMIT * 100)


if __name__ == "__main__":
    unittest.main()
