#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import sys
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable


USERNAME = "fira6007"
OUTPUT_DIR = Path("assets")
CARD_WIDTH = 900
CARD_HEIGHT = 420
ACTIVITY_WIDTH = 1100
ACTIVITY_HEIGHT = 360
LANGUAGE_REPO_LIMIT = 20


def escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def request_json(url: str, token: str | None = None) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "fira6007-profile-assets",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def fetch_all_pages(
    url: str,
    *,
    token: str | None = None,
    fetch_json: Callable[[str, str | None], Any] = request_json,
) -> list[dict[str, Any]]:
    page = 1
    rows: list[dict[str, Any]] = []
    while True:
        separator = "&" if "?" in url else "?"
        batch = fetch_json(f"{url}{separator}per_page=100&page={page}", token)
        if not batch:
            return rows
        rows.extend(batch)
        if len(batch) < 100:
            return rows
        page += 1


def sum_repo_stars(repos: Iterable[dict[str, Any]]) -> int:
    return sum(int(repo.get("stargazers_count", 0) or 0) for repo in repos)


def latest_repo_update(repos: Iterable[dict[str, Any]]) -> str:
    timestamps = [repo.get("pushed_at") for repo in repos if repo.get("pushed_at")]
    if not timestamps:
        return "No public repository pushes yet"
    latest = max(timestamps)
    return latest[:10]


def top_repositories(repos: Iterable[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    candidates = sorted(
        repos,
        key=lambda repo: (
            int(repo.get("stargazers_count", 0) or 0),
            repo.get("pushed_at") or "",
        ),
        reverse=True,
    )
    return list(candidates[:limit])


def aggregate_languages(language_maps: Iterable[dict[str, int]]) -> list[tuple[str, int, float]]:
    totals: Counter[str] = Counter()
    for language_map in language_maps:
        for name, amount in language_map.items():
            totals[name] += int(amount)
    grand_total = sum(totals.values())
    if grand_total <= 0:
        return []
    ordered = sorted(totals.items(), key=lambda item: (-item[1], item[0].lower()))
    return [(name, amount, (amount / grand_total) * 100) for name, amount in ordered]


def bucket_public_events(
    events: Iterable[dict[str, Any]],
    *,
    today: dt.date,
    days: int = 14,
) -> tuple[list[int], int, int]:
    counts = [0] * days
    touched_repos: set[str] = set()
    for event in events:
        created_at = event.get("created_at")
        repo_name = ((event.get("repo") or {}).get("name")) or ""
        if not created_at:
            continue
        event_date = dt.datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
        delta = (today - event_date).days
        if 0 <= delta < days:
            counts[days - delta - 1] += 1
            if repo_name:
                touched_repos.add(repo_name)
    return counts, sum(counts), len(touched_repos)


def format_number(value: int) -> str:
    return f"{value:,}"


def card_shell(title: str, subtitle: str, width: int, height: int, body: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">{escape(title)}</title>
  <desc id="desc">{escape(subtitle)}</desc>
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#020617" />
      <stop offset="100%" stop-color="#111827" />
    </linearGradient>
    <linearGradient id="edge" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#22d3ee" />
      <stop offset="50%" stop-color="#60a5fa" />
      <stop offset="100%" stop-color="#a78bfa" />
    </linearGradient>
    <style>
      text {{
        font-family: "Segoe UI", Arial, sans-serif;
      }}
      .label {{
        fill: #93c5fd;
        font-size: 18px;
      }}
      .value {{
        fill: #f8fafc;
        font-size: 32px;
        font-weight: 700;
      }}
      .title {{
        fill: #f8fafc;
        font-size: 34px;
        font-weight: 700;
      }}
      .subtitle {{
        fill: #cbd5e1;
        font-size: 18px;
      }}
      .muted {{
        fill: #94a3b8;
        font-size: 15px;
      }}
    </style>
  </defs>
  <rect width="{width}" height="{height}" rx="28" fill="url(#bg)" />
  <rect x="1.5" y="1.5" width="{width - 3}" height="{height - 3}" rx="26.5" fill="none" stroke="url(#edge)" stroke-width="3" opacity="0.95" />
  <text class="title" x="42" y="64">{escape(title)}</text>
  <text class="subtitle" x="42" y="96">{escape(subtitle)}</text>
  {body}
</svg>
"""


def build_overview_svg(
    profile: dict[str, Any],
    repos: list[dict[str, Any]],
    generated_on: str,
) -> str:
    metrics = [
        ("Public repos", format_number(int(profile.get("public_repos", 0) or 0)), 42, 146),
        ("Followers", format_number(int(profile.get("followers", 0) or 0)), 250, 146),
        ("Following", format_number(int(profile.get("following", 0) or 0)), 458, 146),
        ("Public stars", format_number(sum_repo_stars(repos)), 666, 146),
    ]

    metric_boxes = []
    for label, value, x, y in metrics:
        metric_boxes.append(
            f"""
  <rect x="{x}" y="{y}" width="192" height="104" rx="20" fill="#0f172a" opacity="0.92" stroke="#1d4ed8" stroke-width="1.1" />
  <text class="label" x="{x + 18}" y="{y + 34}">{escape(label)}</text>
  <text class="value" x="{x + 18}" y="{y + 74}">{escape(value)}</text>"""
        )

    repo_rows = []
    for index, repo in enumerate(top_repositories(repos), start=1):
        y = 308 + ((index - 1) * 28)
        row = f"""  <text class="label" x="42" y="{y}">{index}.</text>
  <text class="subtitle" x="66" y="{y}">{escape(repo.get('name', 'Unnamed repository'))}</text>
  <text class="muted" x="632" y="{y}">{escape(format_number(int(repo.get('stargazers_count', 0) or 0)))} ★</text>
  <text class="muted" x="726" y="{y}">updated {escape((repo.get('pushed_at') or '')[:10] or 'unknown')}</text>"""
        repo_rows.append(row)

    body = "\n".join(metric_boxes)
    body += f"""
  <text class="label" x="42" y="280">Highlighted public repositories by stars</text>
  {"".join(repo_rows) if repo_rows else '<text class="muted" x="42" y="308">No public repositories to summarize yet.</text>'}
  <text class="muted" x="42" y="388">Latest public repository push: {escape(latest_repo_update(repos))}</text>
  <text class="muted" x="632" y="388">Refreshed {escape(generated_on)}</text>"""
    return card_shell(
        "GitHub overview",
        "Public GitHub profile snapshot hosted in this repository",
        CARD_WIDTH,
        CARD_HEIGHT,
        body,
    )


def language_color(index: int) -> str:
    palette = ["#22d3ee", "#60a5fa", "#818cf8", "#a78bfa", "#f472b6", "#fb7185"]
    return palette[index % len(palette)]


def build_languages_svg(languages: list[tuple[str, int, float]], generated_on: str) -> str:
    rows = []
    top_languages = languages[:6]
    for index, (language, _, percentage) in enumerate(top_languages):
        y = 148 + (index * 42)
        bar_width = max(42, round((percentage / 100) * 444))
        color = language_color(index)
        rows.append(
            f"""
  <text class="label" x="42" y="{y}">{escape(language)}</text>
  <text class="muted" x="810" y="{y}">{escape(f'{percentage:.1f}%')}</text>
  <rect x="240" y="{y - 16}" width="460" height="14" rx="7" fill="#1f2937" />
  <rect x="240" y="{y - 16}" width="{bar_width}" height="14" rx="7" fill="{color}" />"""
        )

    body = f"""
  <text class="label" x="42" y="126">Public repository code footprint by bytes</text>
  {''.join(rows) if rows else '<text class="muted" x="42" y="170">Language data is not available yet.</text>'}
  <text class="muted" x="42" y="388">Language data reflects public repository code, not proficiency.</text>
  <text class="muted" x="664" y="388">Refreshed {escape(generated_on)}</text>"""
    return card_shell(
        "Repository languages",
        f"Aggregated from up to {LANGUAGE_REPO_LIMIT} recently updated public repositories",
        CARD_WIDTH,
        CARD_HEIGHT,
        body,
    )


def build_activity_svg(
    daily_counts: list[int],
    total_events: int,
    touched_repos: int,
    generated_on: str,
) -> str:
    max_count = max(daily_counts) if daily_counts else 0
    bar_width = 48
    gap = 20
    bars = []
    for index, count in enumerate(daily_counts):
        x = 66 + (index * (bar_width + gap))
        height = 28 if max_count == 0 else round((count / max_count) * 132)
        y = 254 - height
        bars.append(
            f"""
  <rect x="{x}" y="{y}" width="{bar_width}" height="{height}" rx="14" fill="{language_color(index)}" opacity="0.95" />
  <text class="muted" x="{x + 13}" y="284">D{index + 1}</text>
  <text class="muted" x="{x + 12}" y="{y - 10}">{escape(count)}</text>"""
        )

    body = f"""
  <rect x="42" y="122" width="252" height="88" rx="20" fill="#0f172a" stroke="#155e75" stroke-width="1.1" />
  <rect x="316" y="122" width="252" height="88" rx="20" fill="#0f172a" stroke="#1d4ed8" stroke-width="1.1" />
  <rect x="590" y="122" width="468" height="88" rx="20" fill="#0f172a" stroke="#7c3aed" stroke-width="1.1" />
  <text class="label" x="60" y="156">Window</text>
  <text class="value" x="60" y="194">14 days</text>
  <text class="label" x="334" y="156">Public events</text>
  <text class="value" x="334" y="194">{escape(format_number(total_events))}</text>
  <text class="label" x="608" y="156">Touched repositories in feed</text>
  <text class="value" x="608" y="194">{escape(format_number(touched_repos))}</text>
  {''.join(bars)}
  <text class="muted" x="42" y="328">Based on GitHub's recent public event feed. This is not a complete contribution graph.</text>
  <text class="muted" x="770" y="328">Refreshed {escape(generated_on)}</text>"""
    return card_shell(
        "Recent public activity",
        "A limited-scope view of recent public events instead of a third-party activity graph",
        ACTIVITY_WIDTH,
        ACTIVITY_HEIGHT,
        body,
    )


def build_unavailable_svg(title: str, subtitle: str, detail: str, width: int, height: int) -> str:
    body = f"""
  <rect x="42" y="136" width="{width - 84}" height="{height - 208}" rx="24" fill="#0f172a" stroke="#334155" stroke-width="1.1" />
  <text class="value" x="42" y="210">Temporarily unavailable</text>
  <text class="subtitle" x="42" y="248">{escape(detail)}</text>
  <text class="muted" x="42" y="{height - 42}">See https://github.com/fira6007 and the repositories tab for live public data.</text>"""
    return card_shell(title, subtitle, width, height, body)


def write_asset(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(content, encoding="utf-8")
    os.replace(temporary_path, path)


def render_assets(
    username: str,
    output_dir: Path,
    *,
    token: str | None = None,
    today: dt.date | None = None,
    fetcher: Callable[[str, str | None], Any] = request_json,
) -> dict[str, str]:
    if today is None:
        today = dt.datetime.now(dt.timezone.utc).date()
    generated_on = today.isoformat()
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings: dict[str, str] = {}

    profile: dict[str, Any] | None = None
    repos: list[dict[str, Any]] | None = None
    profile_error: Exception | None = None
    repo_error: Exception | None = None

    try:
        profile = fetcher(f"https://api.github.com/users/{username}", token)
    except Exception as exc:  # pragma: no cover - exercised via tests with injected fetcher
        profile_error = exc

    try:
        repos = fetch_all_pages(
            f"https://api.github.com/users/{username}/repos?type=owner&sort=updated",
            token=token,
            fetch_json=fetcher,
        )
    except Exception as exc:  # pragma: no cover - exercised via tests with injected fetcher
        repo_error = exc

    if profile is not None and repos is not None:
        write_asset(output_dir / "github-overview.svg", build_overview_svg(profile, repos, generated_on))
    else:
        warning_detail = "; ".join(
            str(error) for error in (profile_error, repo_error) if error is not None
        ) or "profile data unavailable"
        warnings["github-overview.svg"] = warning_detail
        overview_path = output_dir / "github-overview.svg"
        if not overview_path.exists():
            write_asset(
                overview_path,
                build_unavailable_svg(
                    "GitHub overview",
                    "Public GitHub profile snapshot hosted in this repository",
                    "GitHub profile data could not be fetched during this refresh.",
                    CARD_WIDTH,
                    CARD_HEIGHT,
                ),
            )
    try:
        language_maps = []
        if repos is None:
            raise RuntimeError("Repository list could not be fetched during this refresh.")
        for repo in repos[:LANGUAGE_REPO_LIMIT]:
            languages_url = repo.get("languages_url")
            if not languages_url:
                continue
            language_maps.append(fetcher(languages_url, token))
        write_asset(
            output_dir / "github-languages.svg",
            build_languages_svg(aggregate_languages(language_maps), generated_on),
        )
    except Exception as exc:  # pragma: no cover - exercised via tests with injected fetcher
        warnings["github-languages.svg"] = str(exc)
        language_path = output_dir / "github-languages.svg"
        if not language_path.exists():
            write_asset(
                language_path,
                build_unavailable_svg(
                    "Repository languages",
                    f"Aggregated from up to {LANGUAGE_REPO_LIMIT} recently updated public repositories",
                    "Repository language data could not be fetched during this refresh.",
                    CARD_WIDTH,
                    CARD_HEIGHT,
                ),
            )

    try:
        events = fetch_all_pages(
            f"https://api.github.com/users/{username}/events/public",
            token=token,
            fetch_json=fetcher,
        )
        daily_counts, total_events, touched_repos = bucket_public_events(events, today=today)
        write_asset(
            output_dir / "github-activity.svg",
            build_activity_svg(daily_counts, total_events, touched_repos, generated_on),
        )
    except Exception as exc:  # pragma: no cover - exercised via tests with injected fetcher
        warnings["github-activity.svg"] = str(exc)
        activity_path = output_dir / "github-activity.svg"
        if not activity_path.exists():
            write_asset(
                activity_path,
                build_unavailable_svg(
                    "Recent public activity",
                    "A limited-scope view of recent public events instead of a third-party activity graph",
                    "Recent public activity could not be fetched during this refresh.",
                    ACTIVITY_WIDTH,
                    ACTIVITY_HEIGHT,
                ),
            )

    return warnings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate repository-hosted profile SVG cards.")
    parser.add_argument("--username", default=USERNAME)
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    warnings = render_assets(args.username, Path(args.output_dir), token=args.token)
    for name, warning in warnings.items():
        print(f"warning: preserved or recreated {name} after refresh issue: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
