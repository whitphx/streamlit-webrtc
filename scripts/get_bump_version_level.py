import warnings
from typing import Literal, Optional

from scriv.scriv import Scriv

SEMVER_LEVELS = Literal["major", "minor", "patch"]


CATEGORY_SEMVER_MAP: dict[str, SEMVER_LEVELS] = {
    "Added": "minor",
    "Changed": "minor",
    "Deprecated": "minor",
    "Removed": "major",
    "Fixed": "patch",
    "Security": "patch",
    "Chore": "patch",
}


def get_bump_level() -> Optional[SEMVER_LEVELS]:
    scriv = Scriv()

    frags = scriv.fragments_to_combine()
    changelog_entries = scriv.combine_fragments(frags)
    changelog_keys = list(changelog_entries.keys())
    changelog_levels: set[SEMVER_LEVELS] = set()
    for changelog_key in changelog_keys:
        if changelog_key in CATEGORY_SEMVER_MAP:
            changelog_levels.add(CATEGORY_SEMVER_MAP[changelog_key])
        else:
            warnings.warn(
                f"Warning: Unrecognized changelog category '{changelog_key}'. It's treated as 'patch' for now."
            )
            changelog_levels.add("patch")

    if "major" in changelog_levels:
        return "major"
    elif "minor" in changelog_levels:
        return "minor"
    elif "patch" in changelog_levels:
        return "patch"
    else:
        return None


if __name__ == "__main__":
    level = get_bump_level()
    if level is None:
        print("No version bump needed.")
        exit(1)

    print(level)
