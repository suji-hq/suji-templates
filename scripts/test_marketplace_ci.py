import contextlib
import io
import json
import unittest
from argparse import Namespace
from unittest.mock import patch
import marketplace_ci as ci


def template(repo, tag):
    return ({"slug": "ghost", "version": tag}, {"services": {"ghost": {"image": repo + ":" + tag}}}, "unchanged")


class ManagedUpstreamTests(unittest.TestCase):
    def poll(self, current="6.72.0-suji.1", latest="6.73.0", repo="ghcr.io/suji-hq/marketplace-ghost"):
        output = io.StringIO()
        with patch.object(ci, "load_template", return_value=template(repo, current)), patch.object(ci, "latest_managed_upstream", return_value=latest), patch.dict(ci.os.environ, {}, clear=True), contextlib.redirect_stdout(output):
            status = ci.cmd_poll(Namespace(apps=["ghost"]))
        return status, json.loads(output.getvalue())

    def test_managed_poll_reports_vendor_version_and_workflow_input(self):
        status, result = self.poll()
        self.assertEqual(status, 0)
        self.assertEqual(result["include"], [{"app": "ghost", "current": "6.72.0-suji.1", "candidate": "6.73.0", "version": "6.73.0", "mode": "security-overlay"}])

    def test_same_vendor_version_does_not_rebuild_continuously(self):
        self.assertEqual(self.poll(latest="6.72.0"), (0, {"include": []}))

    def test_older_vendor_release_does_not_downgrade(self):
        self.assertEqual(self.poll(latest="6.71.0"), (0, {"include": []}))

    def test_unknown_managed_mapping_fails_poll_instead_of_claiming_current(self):
        status, _ = self.poll(repo="ghcr.io/suji-hq/marketplace-unknown")
        self.assertEqual(status, 1)

    def test_invalid_managed_tag_fails_closed(self):
        self.assertEqual(self.poll(current="latest")[0], 1)

    def test_manual_dispatch_cannot_bypass_managed_build_review(self):
        compose = "services:\n  ghost:\n    image: ghcr.io/suji-hq/marketplace-ghost:6.72.0-suji.1\n"
        manifest = "slug: ghost\nversion: 6.72.0-suji.1\n"
        args = Namespace(app="ghost", base="HEAD", from_worktree=False, version="6.73.0")
        with patch.object(ci, "git_show", side_effect=lambda ref, path: manifest if path.endswith("manifest.yaml") else compose), patch.object(ci, "_finish") as finish, patch.object(ci, "image_contract") as docker, patch.object(ci, "boot_test") as boot:
            self.assertEqual(ci.cmd_analyze(args), 0)
        report = finish.call_args.args[0]
        self.assertEqual(report.verdict, "NEEDS_REVIEW")
        self.assertEqual(report.candidate_version, "6.73.0")
        docker.assert_not_called(); boot.assert_not_called()
        self.assertIn("has not been rebuilt or tested", ci.render_markdown(report))
        self.assertNotIn("It starts and serves", ci.render_markdown(report))

    def test_direct_bump_cannot_replace_managed_image(self):
        with patch.object(ci, "load_template", return_value=template("ghcr.io/suji-hq/marketplace-ghost", "6.72.0-suji.1")):
            with self.assertRaisesRegex(ValueError, "reviewed image build"):
                ci.cmd_bump(Namespace(app="ghost", version="6.73.0"))

    def test_github_latest_mapping_preserves_only_hermes_v_prefix(self):
        with patch.object(ci, "_http_json", return_value={"tag_name": "v0.22.4", "draft": False, "prerelease": False}) as fetch:
            self.assertEqual(ci.latest_managed_upstream(ci.MANAGED_UPSTREAMS["hermes"]), "v0.22.4")
            self.assertEqual(ci.latest_managed_upstream(ci.MANAGED_UPSTREAMS["openclaw"]), "0.22.4")
            self.assertIn("api.github.com/repos/openclaw/openclaw/releases/latest", fetch.call_args.args[0])

    def test_prerelease_and_draft_release_rejected(self):
        for flags in [{"prerelease": True}, {"draft": True}, {"tag_name": "v3.0.0-beta"}]:
            with patch.object(ci, "_http_json", return_value={"tag_name": "v3.0.0", **flags}):
                with self.assertRaises(ValueError): ci.latest_managed_upstream(ci.MANAGED_UPSTREAMS["wikijs"])

    def test_vendor_poll_retains_normal_behavior(self):
        output = io.StringIO()
        with patch.object(ci, "load_template", return_value=template("docker.io/ghost", "6.71.0")), patch.object(ci, "registry_tags", return_value=["6.72.0"]), patch.object(ci, "latest_stable", return_value="6.72.0"), patch.dict(ci.os.environ, {}, clear=True), contextlib.redirect_stdout(output):
            self.assertEqual(ci.cmd_poll(Namespace(apps=["ghost"])), 0)
        self.assertEqual(json.loads(output.getvalue())["include"][0]["mode"], "vendor-image")


if __name__ == "__main__": unittest.main()
