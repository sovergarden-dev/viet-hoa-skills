"""Real installer fault injection on a synthetic workspace (needs .NET 8 SDK)."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2]
INSTALLER = SKILL / "scripts" / "install_bientaptay.py"
GENERATOR = SKILL.parents[1] / "gaming" / "viethoa" / "scripts" / "generate_canonical_editor_handoff.py"


def sdk8() -> bool:
    if not shutil.which("dotnet") or not GENERATOR.is_file():
        return False
    result = subprocess.run(["dotnet", "--version"], capture_output=True, text=True)
    return result.returncode == 0 and result.stdout.strip().startswith("8.")


def tree(root: Path) -> dict:
    skip = {"app", "install-receipt.json"}
    out = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_file() and rel.parts[0] not in skip and not {"bin", "obj", "__pycache__"}.intersection(rel.parts):
            out[rel.as_posix()] = path.read_bytes()
    return out


@unittest.skipUnless(sdk8(), ".NET 8 SDK and viethoa companion required")
class InstallFaultTests(unittest.TestCase):
    def test_failed_update_restores_source_config_and_data(self):
        with tempfile.TemporaryDirectory(prefix="bientaptay-fault-") as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            canonical = workspace / "canonical.csv"
            canonical.write_text("key,source,target,state\nk1,Hello,Xin chao,reviewed\n", encoding="utf-8")
            handoff = workspace / "handoff.json"
            gen = subprocess.run([sys.executable, str(GENERATOR), "--workspace", str(workspace), "--canonical", str(canonical),
                                  "--output", str(handoff), "--project-id", "fault", "--key-column", "key", "--source-column", "source",
                                  "--target-column", "target", "--state-column", "state", "--domain", "text"],
                                 capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(gen.returncode, 0, gen.stdout + gen.stderr)
            base = [sys.executable, str(INSTALLER), "--handoff", str(handoff), "--workspace", str(workspace),
                    "--canonical", str(canonical), "--project-name", "Fault"]
            first = subprocess.run(base, capture_output=True, text=True, encoding="utf-8", cwd=tmp, timeout=900)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            app = workspace / "bientaptay"
            (app / "src" / "STALE_MARKER.txt").write_text("keep-me", encoding="utf-8")
            (app / "data" / "glossary.csv").write_bytes(b"term,translation,type,context,status\nA,B,x,,reviewed\n")
            before = tree(app)
            exe_before = (app / "app" / "BienTapTay.exe").read_bytes()
            canonical_before = canonical.read_bytes()
            fault_cwd = Path(tmp) / "fault_cwd"
            fault_cwd.mkdir()
            (fault_cwd / "global.json").write_text(json.dumps({"sdk": {"version": "99.0.0", "rollForward": "disable"}}), encoding="utf-8")
            failed = subprocess.run(base + ["--update", "--reconfigure"], capture_output=True, text=True, encoding="utf-8",
                                    cwd=fault_cwd, timeout=900)
            self.assertNotEqual(failed.returncode, 0, failed.stdout + failed.stderr)
            combined = failed.stdout + failed.stderr
            self.assertIn('Cần .NET 8 SDK', combined)
            self.assertIn('khôi phục', combined)
            self.assertEqual(tree(app), before)
            self.assertFalse((app / ".template-previous").exists())
            self.assertFalse((app / ".template-staging").exists())
            self.assertEqual((app / "app" / "BienTapTay.exe").read_bytes(), exe_before)
            self.assertEqual(canonical.read_bytes(), canonical_before)
            receipt_before = (app / "install-receipt.json").read_bytes()
            (workspace / "global.json").write_text(json.dumps({"sdk": {"version": "99.0.0", "rollForward": "disable"}}), encoding="utf-8")
            published = subprocess.run(base + ["--update", "--reconfigure"], capture_output=True, text=True,
                                       encoding="utf-8", cwd=tmp, timeout=900)
            output = published.stdout + published.stderr
            self.assertNotEqual(published.returncode, 0, output)
            self.assertIn("Step 1/7", output)
            self.assertIn("khôi phục", output)
            self.assertEqual(tree(app), before)
            self.assertEqual((app / "app" / "BienTapTay.exe").read_bytes(), exe_before)
            self.assertEqual((app / "install-receipt.json").read_bytes(), receipt_before)
            self.assertEqual(canonical.read_bytes(), canonical_before)
            self.assertFalse((app / ".template-previous").exists())
            self.assertFalse((app / ".template-staging").exists())


def full_tree(root: Path) -> dict:
    import hashlib
    out = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_file() and not {"bin", "obj", "__pycache__"}.intersection(rel.parts):
            out[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


@unittest.skipUnless(sdk8(), ".NET 8 SDK and viethoa companion required")
class VerifyStageFaultTests(unittest.TestCase):
    def test_verify_stage_failure_restores_app_receipt_and_baseline(self):
        with tempfile.TemporaryDirectory(prefix="bientaptay-verify-fault-") as tmp:
            tmp = Path(tmp)
            skills = tmp / "skills"
            shutil.copytree(SKILL, skills / "software-development" / "bientaptay",
                            ignore=shutil.ignore_patterns("bin", "obj", "__pycache__"))
            shutil.copytree(GENERATOR.parent, skills / "gaming" / "viethoa" / "scripts",
                            ignore=shutil.ignore_patterns("__pycache__"))
            installer = skills / "software-development" / "bientaptay" / "scripts" / "install_bientaptay.py"
            generator = skills / "gaming" / "viethoa" / "scripts" / GENERATOR.name
            workspace = tmp / "ws"
            workspace.mkdir()
            canonical = workspace / "canonical.csv"
            canonical.write_text("key,source,target,state\nk1,Hello,Xin chao,reviewed\n", encoding="utf-8")
            handoff = workspace / "handoff.json"
            gen = subprocess.run([sys.executable, str(generator), "--workspace", str(workspace), "--canonical", str(canonical),
                                  "--output", str(handoff), "--project-id", "verify-fault", "--key-column", "key",
                                  "--source-column", "source", "--target-column", "target", "--state-column", "state",
                                  "--domain", "text"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(gen.returncode, 0, gen.stdout + gen.stderr)
            base = [sys.executable, str(installer), "--handoff", str(handoff), "--workspace", str(workspace),
                    "--canonical", str(canonical), "--project-name", "VerifyFault"]
            first = subprocess.run(base, capture_output=True, text=True, encoding="utf-8", cwd=tmp, timeout=900)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            app = workspace / "bientaptay"
            (app / 'app' / 'rollback-sentinel.bin').write_bytes(b'old release only; must survive recovery')
            before = full_tree(app)
            self.assertIn("install-receipt.json", before)
            self.assertIn("performance-baseline.json", before)
            self.assertTrue(any(key.startswith("app/") for key in before))
            text = installer.read_bytes().decode("utf-8")
            needle = "validate_receipt_count(receipt, translations_after)"
            self.assertIn(needle, text)
            installer.write_bytes(text.replace(needle, "raise ValueError('injected verify-stage fault')", 1).encode("utf-8"))
            failed = subprocess.run(base + ["--update", "--reconfigure"], capture_output=True, text=True,
                                    encoding="utf-8", cwd=tmp, timeout=900)
            output = failed.stdout + failed.stderr
            self.assertNotEqual(failed.returncode, 0, output)
            self.assertIn("injected verify-stage fault", output)
            after = full_tree(app)
            changed = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
            self.assertEqual(changed, [], output[-800:])
            self.assertEqual([p.name for p in app.parent.glob(".*installer-backup")], [])
            self.assertEqual([p.name for p in app.glob(".template-*")], [])


@unittest.skipUnless(sdk8(), ".NET 8 SDK and viethoa companion required")
class InstallerLockTests(unittest.TestCase):
    def test_second_installer_is_refused_without_touching_workspace(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("template_swap", SKILL / "scripts" / "template_swap.py")
        swap = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(swap)
        with tempfile.TemporaryDirectory(prefix="bientaptay-lock-") as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            canonical = workspace / "canonical.csv"
            canonical.write_text("key,source,target,state\nk1,Hello,Xin chao,reviewed\n", encoding="utf-8")
            handoff = workspace / "handoff.json"
            gen = subprocess.run([sys.executable, str(GENERATOR), "--workspace", str(workspace), "--canonical", str(canonical),
                                  "--output", str(handoff), "--project-id", "lock", "--key-column", "key",
                                  "--source-column", "source", "--target-column", "target", "--state-column", "state",
                                  "--domain", "text"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(gen.returncode, 0, gen.stdout + gen.stderr)
            before = {p.relative_to(workspace).as_posix(): p.read_bytes() for p in workspace.rglob("*") if p.is_file()}
            command = [sys.executable, str(INSTALLER), "--handoff", str(handoff), "--workspace", str(workspace),
                       "--canonical", str(canonical), "--project-name", "Lock"]
            with swap.InstallerLock(workspace):
                refused = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", cwd=tmp, timeout=120)
            output = refused.stdout + refused.stderr
            self.assertNotEqual(refused.returncode, 0, output)
            self.assertIn("Installer khác đang chạy", output)
            after = {p.relative_to(workspace).as_posix(): p.read_bytes() for p in workspace.rglob("*")
                     if p.is_file() and p.name != ".bientaptay.installer.lock"}
            before.pop(".bientaptay.installer.lock", None)
            self.assertEqual(after, before)
            self.assertFalse((workspace / "bientaptay").exists())


if __name__ == "__main__":
    unittest.main()
