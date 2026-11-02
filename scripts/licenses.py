#!/usr/bin/env python3
"""The licence gates for the locked environment.

Two jobs, both reading the environment `uv sync --locked` produces, so what is
checked is what is installed rather than what a resolver might pick later:

  check-licenses  every installed distribution carries a licence on the
                  allow-list below, identified by SPDX id.
  notice          regenerate NOTICE from that environment and the header in
                  scripts/notice.tpl.
  check-notice    fail when the committed NOTICE differs from what the
                  environment produces, so a dependency change lands with its
                  attribution.

Usage: licenses.py check-licenses | notice | check-notice
       licenses.py --allowed        print the allow-list, one id per line

Python packaging reports licences three different ways and this reads them in
order of authority: PEP 639 `License-Expression` first, then the
`License ::` classifiers, then the legacy free-text `License` field. Most of
the environment answers on the first, but the legacy field is still the only
answer some distributions give, and it is free text, so the aliases below map
what is actually seen to SPDX ids rather than attempting to parse prose.
"""

from __future__ import annotations

import re
import sys
from importlib.metadata import Distribution, distributions
from pathlib import Path

# The licences the deployed server may redistribute. MPL-2.0 is on it because
# its obligations attach to the MPL-licensed files themselves, which an
# unmodified, unvendored dependency leaves alone. MIT-0, PSF-2.0 and Unlicense
# are on it because they are permissive and appear in this environment;
# Unlicense is a public-domain dedication, so it carries no obligation at all.
# GPL, LGPL and AGPL are off it.
ALLOWED = {
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "MIT",
    "MIT-0",
    "MPL-2.0",
    "PSF-2.0",
    "Unlicense",
}

# Legacy `License` values and `License ::` classifiers seen in this
# environment, mapped to SPDX. "BSD License" does not say which BSD, but both
# BSD-2-Clause and BSD-3-Clause are on the allow-list, so the distinction
# cannot change a verdict.
ALIASES = {
    "apache software license": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "bsd license": "BSD-3-Clause",
    "isc license (iscl)": "ISC",
    "mit license": "MIT",
    "mozilla public license 2.0 (mpl 2.0)": "MPL-2.0",
    "python software foundation license": "PSF-2.0",
    "the unlicense (unlicense)": "Unlicense",
}

CLASSIFIER = "License :: OSI Approved :: "


def _alias(value: str) -> str:
    return ALIASES.get(value.strip().lower(), value.strip())


def resolve(dist: Distribution) -> tuple[str, str]:
    """Return this distribution's licence expression and where it came from."""
    meta = dist.metadata

    expression = meta.get("License-Expression")
    if expression:
        return expression.strip(), "License-Expression"

    classifiers = [
        c[len(CLASSIFIER) :] for c in (meta.get_all("Classifier") or []) if c.startswith(CLASSIFIER)
    ]
    if classifiers:
        return " AND ".join(_alias(c) for c in classifiers), "classifier"

    legacy = meta.get("License")
    if legacy and "\n" not in legacy.strip():
        # Some distributions put several ids in one field, separated by ";".
        return " AND ".join(_alias(p) for p in legacy.split(";")), "License"

    return "", "none"


def identifiers(expression: str) -> list[str]:
    """The licence ids in an SPDX expression, with the operators dropped."""
    tokens = re.split(r"[()\s]+", expression)
    return [t for t in tokens if t and t.upper() not in {"AND", "OR", "WITH"}]


def installed() -> list[Distribution]:
    seen: dict[str, Distribution] = {}
    for dist in distributions():
        name = dist.metadata["Name"]
        # The project itself is not third-party.
        if name and name.lower() != "getting-started-mcp":
            seen[name] = dist
    return [seen[k] for k in sorted(seen, key=str.lower)]


def check_licenses() -> int:
    bad = []
    unknown = []
    for dist in installed():
        expression, source = resolve(dist)
        name = f"{dist.metadata['Name']} {dist.version}"
        if not expression:
            unknown.append(name)
            continue
        offenders = [i for i in identifiers(expression) if i not in ALLOWED]
        if offenders:
            bad.append(f"{name}: {expression} ({source}) -> {', '.join(offenders)}")

    for line in unknown:
        print(f"check-licenses: NO LICENCE METADATA: {line}", file=sys.stderr)
    for line in bad:
        print(f"check-licenses: NOT ALLOWED: {line}", file=sys.stderr)

    if bad or unknown:
        print(
            "check-licenses: FAIL. Every id in a distribution's expression must be on "
            "the allow-list; run 'make licenses-allowed' to print it.",
            file=sys.stderr,
        )
        return 1

    print(
        f"check-licenses: OK. {len(installed())} distributions, every id on the "
        f"allow-list: {', '.join(sorted(ALLOWED))}"
    )
    return 0


def licence_files(dist: Distribution) -> list[tuple[str, str]]:
    """Every licence file the distribution ships, as (name, text).

    A dual-licensed distribution ships one per licence -- packaging carries
    LICENSE, LICENSE.APACHE and LICENSE.BSD -- so all of them are reproduced
    rather than whichever sorts first. Read through locate_file: read_text
    resolves against the .dist-info directory, not the path files() reports.
    """
    out = []
    for entry in sorted(dist.files or [], key=str):
        name = str(entry)
        if not re.search(r"(^|/)(LICEN[CS]E|COPYING)", name.upper()):
            continue
        if name.endswith(".py"):
            continue
        try:
            text = Path(dist.locate_file(entry)).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if text.strip():
            out.append((name.rsplit("/", 1)[-1], text.strip()))
    return out


def render() -> str:
    header = (Path(__file__).parent / "notice.tpl").read_text()
    out = [header.rstrip("\n")]
    for dist in installed():
        expression, _ = resolve(dist)
        out.append("")
        out.append("-" * 76)
        out.append(f"{dist.metadata['Name']} {dist.version}")
        out.append(f"License: {expression or 'not stated in the distribution metadata'}")
        files = licence_files(dist)
        for name, text in files:
            out.append("")
            if len(files) > 1:
                out.append(f"--- {name} ---")
                out.append("")
            out.append(text)
        if not files:
            out.append("")
            out.append("This distribution ships no licence file.")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    command = argv[1]
    notice = Path(__file__).parent.parent / "NOTICE"

    if command == "--allowed":
        print("\n".join(sorted(ALLOWED)))
        return 0
    if command == "check-licenses":
        return check_licenses()
    if command == "notice":
        notice.write_text(render())
        print(f"notice: wrote NOTICE, {len(installed())} distributions")
        return 0
    if command == "check-notice":
        if notice.read_text() != render():
            print(
                "notice: FAIL. NOTICE is stale; run 'make notice' and commit the result.",
                file=sys.stderr,
            )
            return 1
        print("notice: OK. NOTICE matches the locked environment.")
        return 0

    print(f"licenses.py: unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
