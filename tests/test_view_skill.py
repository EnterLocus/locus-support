# SPDX-License-Identifier: Apache-2.0
"""Public-safety, link portability, tool-path, and capability coverage tests for build-a-view."""

from pathlib import Path
import re
import shutil
import tempfile
import unittest
import urllib.parse


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / ".agents" / "skills" / "build-a-view"
LEGACY_REFERENCES = frozenset({
    "skybox-workflow.md",
    "models-and-cost.md",
    "resolution.md",
})
EXPECTED_REFERENCES = LEGACY_REFERENCES | {
    "package-v2-delivery.md",
    "sky-clouds-and-daylight.md",
    "water-and-shore.md",
    "midground-3d.md",
    "video-atmosphere-and-sound.md",
    "space-and-black-hole.md",
}


class BuildAViewSkillTests(unittest.TestCase):
    def test_skill_has_frontmatter_and_indexes_all_references(self):
        skill_md = (SKILL_DIR / "SKILL.md").read_text()
        self.assertTrue(skill_md.startswith("---\n"))
        actual_refs = {path.name for path in (SKILL_DIR / "references").glob("*.md")}
        self.assertEqual(actual_refs, EXPECTED_REFERENCES)
        for name in sorted(EXPECTED_REFERENCES):
            with self.subTest(reference=name):
                self.assertIn(f"references/{name}", skill_md)

    def test_skill_is_public_safe_and_has_portable_links_and_valid_repo_paths(self):
        with tempfile.TemporaryDirectory(prefix="locus-view-skill-") as directory:
            copied = (Path(directory) / SKILL_DIR.name).resolve()
            shutil.copytree(SKILL_DIR, copied)
            combined_parts = []
            links_checked = 0
            repo_paths_checked = 0

            for path in sorted(copied.rglob("*.md")):
                content = path.read_text()
                combined_parts.append(content)
                rel = path.relative_to(copied)
                with self.subTest(path=str(rel)):
                    for private_detail in (
                        "/Users/",
                        "/Volumes/",
                        "Dropbox",
                        "Locus Dev",
                        "model-preview/",
                        "--simulator-head-pose",
                        "LOCUS_SIGNING",
                        "creator_combined_cap",
                        "generator/",
                        "experiments/",
                    ):
                        self.assertNotIn(private_detail, content)
                    self.assertNotRegex(
                        content, r"github\.com/EnterLocus/locus(?:/|[)#\s]|$)"
                    )
                    self.assertNotRegex(
                        content,
                        r"(?i)train(?:ing)? (?:or fine-tune )?(?:an )?AI models?|outside Locus",
                    )

                targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", content)
                for target in targets:
                    parsed = urllib.parse.urlsplit(target)
                    if parsed.scheme or parsed.netloc or not parsed.path:
                        continue
                    if path.name in LEGACY_REFERENCES and target.startswith("../../../../"):
                        resolved = (ROOT / parsed.path.replace("../../../../", "")).resolve()
                        self.assertTrue(resolved.is_relative_to(ROOT), target)
                        self.assertTrue(resolved.is_file(), target)
                    else:
                        resolved = (path.parent / urllib.parse.unquote(parsed.path)).resolve()
                        self.assertTrue(resolved.is_relative_to(copied), target)
                        self.assertTrue(resolved.is_file(), target)
                    links_checked += 1

                for repo_rel in re.findall(
                    r"(?:tools/[^\s`'\"),]+\.(?:py|json)|schemas/[^\s`'\"),]+\.json)",
                    content,
                ):
                    self.assertTrue((ROOT / repo_rel).is_file(), f"{rel}: missing {repo_rel}")
                    repo_paths_checked += 1

            self.assertGreater(links_checked, 0)
            self.assertGreater(repo_paths_checked, 0)

            combined = "\n".join(combined_parts)
            for required in (
                "pack_locusplace.py",
                "validate_locusplace.py",
                "--current-app-version",
                "sunFreeSky",
                "panoramaBlend",
                "gpuTextures",
                "shore",
                "flowingWater",
                "primvars:st",
                "primvars:displayColor",
                "point-lights.json",
                "fireflies",
                "celestial",
                "nearOrbit",
                "blackHole",
                "azimuthDegrees",
            ):
                with self.subTest(capability_term=required):
                    self.assertIn(required, combined)


if __name__ == "__main__":
    unittest.main()
