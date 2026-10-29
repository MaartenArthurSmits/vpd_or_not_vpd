"""Print a concise Markdown summary of pytest JUnit XML files (for GITHUB_STEP_SUMMARY)."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

LABELS = {"1": "Scientific + unit", "2": "Streamlit AppTest", "3": "Playwright browser", "4": "Export validation"}


def summarize(path: Path):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root)
    tests = sum(int(s.get("tests", 0)) for s in suites)
    fails = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    skips = sum(int(s.get("skipped", 0)) for s in suites)
    secs = sum(float(s.get("time", 0)) for s in suites)
    failed = [f"{c.get('classname')}::{c.get('name')}" for s in suites for c in s.iter("testcase")
              if c.find("failure") is not None or c.find("error") is not None]
    return tests, fails, skips, secs, failed


def main(paths):
    print("## Test summary\n")
    print("| Suite | Tests | Passed | Failed | Skipped | Time (s) |")
    print("|---|---|---|---|---|---|")
    all_failed = []
    for p in sorted(Path(x) for x in paths):
        tests, fails, skips, secs, failed = summarize(p)
        label = LABELS.get(p.stem.split("-")[1], p.stem)
        print(f"| {label} | {tests} | {tests - fails - skips} | {fails} | {skips} | {secs:.1f} |")
        all_failed += failed
    if all_failed:
        print("\n**Failed tests**\n")
        for name in all_failed:
            print(f"- `{name}`")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
