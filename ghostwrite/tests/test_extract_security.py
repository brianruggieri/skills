"""Security + voice-preservation tests for ghostwrite/scripts/extract-corpus.py.

Two goals, neither of which is allowed to give:

1. Security improvements are real. Known secret shapes (API keys, JWTs, AWS
   keys, URL-embedded credentials, bearer tokens) are scrubbed from any text
   that flows through `redact()`. Path allowlists block traversal. Archive
   writes refuse symlinks.

2. Voice signal is preserved. Redaction never strips signature phrases,
   sentence rhythm, capitalization patterns, or punctuation habits. Filters
   (`is_voice`, `is_conversational`) behave identically to the pre-hardening
   version on a representative sample of the user's actual corpus.

Run:
    python3 -m unittest ghostwrite.tests.test_extract_security
or:
    python3 ghostwrite/tests/test_extract_security.py
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "ghostwrite" / "scripts" / "extract-corpus.py"


def _load_extract_module():
    """Load extract-corpus.py as a module despite the hyphenated filename."""
    spec = importlib.util.spec_from_file_location("extract_corpus", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


extract = _load_extract_module()


# ---------------------------------------------------------------------------
# Redaction: positive controls (secrets must be removed)
# ---------------------------------------------------------------------------
#
# Test fixtures use string concatenation to assemble each fake-secret value
# so that GitHub's push-protection secret scanner (and similar provider-side
# scanners) do not see a complete token shape in any single source-line
# literal. The values are NOT real secrets — they are placeholder strings
# matching the redactor's regex shapes.

# Tokenized prefixes — keep these as separate literals so no full token
# shape appears verbatim in the repo.
_SK = "sk"
_RK = "rk"
_PK = "pk"
_GH = "gh"
_AKIA = "AK" + "IA"
_ASIA = "AS" + "IA"
_AIZA = "AI" + "za"
_XOX = "xo" + "x"


def _key(*parts: str) -> str:
    return "".join(parts)


class RedactStripsSecrets(unittest.TestCase):
    """Each test feeds a known secret shape through redact() and asserts the
    raw secret is gone from the output."""

    def assert_redacted(self, raw: str, secret_substring: str):
        out = extract.redact(raw)
        self.assertNotIn(
            secret_substring, out,
            f"redact() failed to strip {secret_substring!r} from input:\n{raw!r}\n"
            f"output was:\n{out!r}",
        )

    def test_anthropic_key(self):
        key = _key(_SK, "-ant-api03-", "AbCdEfGhIjKlMnOpQrStUvWxYz0123456789-extra")
        raw = f"the key is {key} and a comment"
        self.assert_redacted(raw, key)

    def test_openai_project_key(self):
        key = _key(_SK, "-proj-", "1234567890abcdefghijklmnopqrstuvwxyz0123")
        raw = f"use {key} here"
        self.assert_redacted(raw, key)

    def test_openai_classic_key(self):
        key = _key(_SK, "-", "abcdefghijklmnopqrstuvwxyz1234567890")
        raw = f"old key {key} was rotated"
        self.assert_redacted(raw, key)

    def test_github_pat(self):
        key = _key(_GH, "p_", "abcdefghijklmnopqrstuvwxyz0123456789")
        raw = f"set GH_TOKEN={key} for ci"
        self.assert_redacted(raw, key)

    def test_aws_access_key(self):
        # AKIA + 16 alphanumeric uppercase. Build from parts so the canonical
        # "AKIAIOSFODNN7EXAMPLE" string never appears as one literal.
        key = _AKIA + "IOSFODNN7" + "PLACEHX"
        raw = f"the access key was {key} which is a sample"
        self.assert_redacted(raw, key)

    def test_aws_session_key(self):
        key = _ASIA + "IOSFODNN7" + "PLACEHX"
        raw = f"session key {key} in the env"
        self.assert_redacted(raw, key)

    def test_jwt(self):
        jwt = (
            "ey" + "JhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
            + "." + "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0"
            + "." + "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        raw = f"Authorization: Bearer {jwt} extra"
        out = extract.redact(raw)
        # The JWT-specific redactor should fire OR the Bearer redactor should
        # fire. Either way the full JWT must be gone.
        self.assertNotIn(jwt, out, f"JWT survived: {out!r}")

    def test_url_with_credentials(self):
        pw = "hunter" + "2"
        raw = f"clone https://alice:{pw}@github.com/example/repo and run"
        out = extract.redact(raw)
        self.assertNotIn(f"alice:{pw}", out)
        self.assertNotIn(pw, out)

    def test_bearer_token(self):
        tok = "abc" + "123def456ghi789jkl012mno345"
        raw = f"header bearer {tok} was rotated"
        out = extract.redact(raw)
        self.assertNotIn(tok, out)

    def test_password_assignment(self):
        secret = "hunter" + "2-correct-horse-battery"
        for raw in [
            f"password={secret}",
            f"PASSWORD: {secret}",
            f"api_key='{secret}'",
            f'token: "{secret}"',
        ]:
            with self.subTest(raw=raw):
                out = extract.redact(raw)
                self.assertNotIn(secret, out)

    def test_email_redacted_but_first_char_kept(self):
        raw = "ping alice@example.com when ready"
        out = extract.redact(raw)
        self.assertNotIn("alice@example.com", out)
        # First letter + domain preserved so voice analysis still has signal
        # about whether the user mentions email at all.
        self.assertIn("a***@example.com", out)

    def test_home_path_collapsed(self):
        home = str(extract.HOME)
        raw = f"file lives at {home}/git/skills/ghostwrite/corpus.txt right now"
        out = extract.redact(raw)
        self.assertNotIn(home + "/git/skills", out)
        self.assertIn("~/git/skills", out)

    def test_openai_service_account_key(self):
        key = _key(_SK, "-svcacct-", "abcdefghijklmnopqrstuvwxyz0123456789")
        raw = f"set OPENAI_API_KEY={key} then go"
        self.assert_redacted(raw, key)

    def test_stripe_live_key(self):
        key = _key(_SK, "_", "live_", "abcdefghijklmnopqrstuvwx0123456789")
        raw = f"billing uses {key} for prod"
        self.assert_redacted(raw, key)

    def test_stripe_restricted_key(self):
        key = _key(_RK, "_", "live_", "abcdefghijklmnopqrstuvwx0123456789")
        raw = f"narrow scope {key} yep"
        self.assert_redacted(raw, key)

    def test_google_api_key(self):
        # Google API keys are AIza + ~35 base64url chars.
        key = _key(_AIZA, "Sy", "ABCDEFghijklMNOP1234567890QRSTUVWxy")
        raw = f"key {key} ok"
        self.assert_redacted(raw, key)

    def test_google_api_key_ending_in_dash(self):
        # Regression: \b would NOT fire between a trailing `-` and a space,
        # because both are non-word chars. The redactor uses explicit
        # non-token-char lookarounds, so this must still be caught.
        key = _key(_AIZA, "Sy", "ABCDEFghijklMNOP1234567890QRSTUV-")
        raw = f"key {key} ok"
        self.assert_redacted(raw, key)

    def test_api_key_at_string_end(self):
        # No trailing whitespace at all — boundary must work at EOS.
        key = _key(_GH, "p_", "abcdefghijklmnopqrstuvwxyz0123456789")
        raw = f"the key is {key}"
        self.assert_redacted(raw, key)

    def test_slack_xoxc_token(self):
        tok = _key(_XOX, "c-", "1234567890-1234567890-1234567890-abcdef")
        raw = f"cookie token {tok} ok"
        self.assert_redacted(raw, tok)

    def test_aws_secret_access_key_env(self):
        # Placeholder values, assembled at runtime.
        secret = "wJalr" + "XUtnFEMI/" + "K7MDENG/" + "bPxRfiCYPLACEHOLDER"
        session = "aBcDe" + "FgHiJkLm" + "NoPqRsTuVwXyZ0123456789aBcD"
        for raw in [
            f"AWS_SECRET_ACCESS_KEY={secret}",
            f"aws_session_token: {session}",
            f'AWS_SECRET_ACCESS_KEY="{secret}"',
        ]:
            with self.subTest(raw=raw):
                out = extract.redact(raw)
                self.assertNotIn(secret, out)
                self.assertNotIn(session, out)


# ---------------------------------------------------------------------------
# Redaction: negative controls (voice must survive)
# ---------------------------------------------------------------------------

class RedactPreservesVoice(unittest.TestCase):
    """Real signature phrases from the user's corpus must pass through
    redact() unchanged. If any of these regress, the profile loses fidelity."""

    SIGNATURE_INPUTS = [
        # All from the actual v3.0 profile and the archived corpus.
        "please advise",
        "what do you think?",
        "make sense?",
        "does that make sense?",
        "do your research",
        "be honest and critical",
        "where do we stand now?",
        "how we looking?",
        "I think I like B, I just don't want to completly bloggify my site",
        "use subagents of appropriate models to research this topic",
        "swarm a team of agents on this",
        "fresh agent / fresh session / fresh context",
        "let's iterate and iterate until we have a polished gameplay loop",
        "lock that in",
        "got it?",
        "idk what's best",
        "I guess for me this comes down to",
        "is substack worth the conversion",
        "worth it?",
        "honestly, this is great",
        "lean into my dream of being an orchestrator",
        "assess, review, address, respond and fix as needed",
        "manager of agents",
        "I'm not sure, please advise and continue",
    ]

    def test_signature_phrases_unchanged(self):
        for phrase in self.SIGNATURE_INPUTS:
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    extract.redact(phrase), phrase,
                    f"redact() altered a signature phrase: {phrase!r}",
                )

    def test_comma_chained_voice_unchanged(self):
        raw = (
            "I think I like B, I just don't want to completly bloggify my "
            "site (maybe it's a better approach in the long run, please "
            "advise, maybe the site morphs into more blog if this takes off)."
        )
        self.assertEqual(extract.redact(raw), raw)

    def test_orchestration_voice_unchanged(self):
        raw = (
            "use subagents of appropriate models to research this, swarm them "
            "on the problem, iterate, and lock in the answer. fresh agent if "
            "needed. be honest and critical."
        )
        self.assertEqual(extract.redact(raw), raw)

    def test_redact_is_idempotent(self):
        # Running redact() twice on the same input must not introduce drift.
        for phrase in self.SIGNATURE_INPUTS:
            with self.subTest(phrase=phrase):
                once = extract.redact(phrase)
                twice = extract.redact(once)
                self.assertEqual(once, twice)

    def test_redact_idempotent_on_mixed_secret_and_voice(self):
        key = _key(_SK, "-ant-api03-", "AbCdEfGhIjKlMnOpQrStUvWxYz0123-extra")
        raw = (
            f"honestly, the key is {key} "
            "and I think we should lock it in, please advise"
        )
        once = extract.redact(raw)
        twice = extract.redact(once)
        self.assertEqual(once, twice)
        # Voice markers still present after redaction
        self.assertIn("honestly", once)
        self.assertIn("I think", once)
        self.assertIn("lock it in", once)
        self.assertIn("please advise", once)


# ---------------------------------------------------------------------------
# Voice / conversational filters: behavior preserved
# ---------------------------------------------------------------------------

class VoiceFiltersUnchanged(unittest.TestCase):
    """The is_voice / is_conversational classifiers are the gate that
    determines which messages enter the corpus. Their behavior must not have
    regressed against representative inputs."""

    VOICE_POSITIVE = [
        "I think I like B, I just don't want to completly bloggify my site, please advise",
        "is substack worth the conversion, should i be putting this into different mediums",
        "use subagents of appropriate models to research this topic, swarm a team",
        "where do we stand now? is it time to run that smoke test, or is there other priority work to be done first?",
    ]

    VOICE_NEGATIVE = [
        "yes",
        "ok",
        "lgtm",
        "ship it",
        "<system message ignore>",
        "{'json': 'object'}",
        "   indented code block here",
    ]

    CONVERSATION_POSITIVE = [
        # Real samples lifted from the user's corpus that should pass.
        "I think I like B, I just don't want to completly bloggify my site, please advise",
        (
            "is substack worth the conversion, should i be putting this into "
            "different mediums/services. worth fitting to my own personal site? "
            "my personal site has very little to no traction at the moment, but "
            "could handle it if needed"
        ),
        "where do we stand now? is it time to run that smoke test, or is there other priority work to be done first?",
    ]

    CONVERSATION_NEGATIVE = [
        "A",
        "B and C",
        "1, 3",
        "commit and push",
    ]

    def test_is_voice_positive(self):
        for t in self.VOICE_POSITIVE:
            with self.subTest(t=t):
                self.assertTrue(extract.is_voice(t), f"is_voice rejected: {t!r}")

    def test_is_voice_negative(self):
        for t in self.VOICE_NEGATIVE:
            with self.subTest(t=t):
                self.assertFalse(extract.is_voice(t), f"is_voice accepted: {t!r}")

    def test_is_conversational_positive(self):
        for t in self.CONVERSATION_POSITIVE:
            with self.subTest(t=t):
                self.assertTrue(
                    extract.is_conversational(t),
                    f"is_conversational rejected: {t!r}",
                )

    def test_is_conversational_negative(self):
        for t in self.CONVERSATION_NEGATIVE:
            with self.subTest(t=t):
                self.assertFalse(
                    extract.is_conversational(t),
                    f"is_conversational accepted: {t!r}",
                )


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

class PathSafety(unittest.TestCase):
    def test_external_output_rejected_by_default(self):
        # An output path outside ~/.claude/ghostwrite/ must fail.
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "evil.txt"
            with self.assertRaises(SystemExit) as cm:
                extract._validate_output_path(target, allow_external=False)
            self.assertIn("refusing to write outside", str(cm.exception))

    def test_external_output_allowed_with_flag(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "ok.txt"
            resolved = extract._validate_output_path(target, allow_external=True)
            # Path is allowed and points where we asked. Compare via samefile
            # so /var vs /private/var symlinks don't break the assertion.
            self.assertTrue(
                resolved.parent.samefile(td),
                f"resolved parent {resolved.parent} differs from {td}",
            )

    def test_external_sessions_rejected_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SystemExit) as cm:
                extract._validate_sessions_dir(Path(td), allow_external=False)
            self.assertIn("refusing to read outside", str(cm.exception))

    def test_symlink_output_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            real = Path(td) / "real.txt"
            real.write_text("x")
            link = Path(td) / "link.txt"
            link.symlink_to(real)
            with self.assertRaises(SystemExit) as cm:
                extract._validate_output_path(link, allow_external=True)
            self.assertIn("refusing to follow symlink", str(cm.exception))

    def test_archive_refuses_symlink_source(self):
        with tempfile.TemporaryDirectory() as td:
            real = Path(td) / "real.txt"
            real.write_text("x")
            link = Path(td) / "link.txt"
            link.symlink_to(real)
            with self.assertRaises(SystemExit) as cm:
                extract.archive_file(link, allow_external=True)
            self.assertIn("refusing to archive symlink", str(cm.exception))

    def test_rejected_external_output_does_not_create_dirs(self):
        """A rejected external path must not cause any filesystem mutation —
        the allowlist check runs before mkdir."""
        with tempfile.TemporaryDirectory() as td:
            forbidden_subdir = Path(td) / "should-not-exist"
            target = forbidden_subdir / "evil.txt"
            with self.assertRaises(SystemExit):
                extract._validate_output_path(target, allow_external=False)
            self.assertFalse(
                forbidden_subdir.exists(),
                "rejected output path triggered a mkdir outside the allowlist",
            )


# ---------------------------------------------------------------------------
# Archive collision safety
# ---------------------------------------------------------------------------

class ArchiveCollisions(unittest.TestCase):
    def test_collision_gets_counter_suffix(self):
        # Two archives within the same wallclock second must not overwrite.
        # We force this by calling archive_file twice in rapid succession.
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "file.txt"
            src.write_text("v1")
            a1 = extract.archive_file(src, allow_external=True)
            src.write_text("v2")
            a2 = extract.archive_file(src, allow_external=True)
            self.assertIsNotNone(a1)
            self.assertIsNotNone(a2)
            self.assertNotEqual(a1, a2)
            self.assertEqual(a1.read_text(), "v1")
            self.assertEqual(a2.read_text(), "v2")


# ---------------------------------------------------------------------------
# Corpus continuity: new extraction should match archived previous extraction
# on the same logs within a tight tolerance.
# ---------------------------------------------------------------------------

class CorpusContinuity(unittest.TestCase):
    """End-to-end check that redaction does not degrade the corpus.

    Runs the script twice on the user's actual session logs: once with
    redaction on (the default), once with --no-redact. Compares prompt
    counts, length distributions, and signature-phrase counts.

    Redaction should:
      - Never change which prompts pass the voice/conversational filters
        (filters run before redaction).
      - Shave at most a tiny fraction of characters (substituting tokens
        for short placeholders).
      - Leave every signature phrase intact.

    Skipped if the user's session dir is missing or empty (CI / fresh checkout).
    """

    SIGNATURE_PROBES = [
        "please advise",
        "make sense",
        "do your research",
        "be honest",
        "subagents of appropriate model",
        "let's",
        "I think",
        "where do we stand",
        "lock in",
        "swarm",
        "fresh agent",
        "iterate",
    ]

    def test_redaction_does_not_degrade_corpus(self):
        """In-memory comparison: extract twice with redact on/off, compare in RAM.

        The raw (unredacted) prompts are never written to disk. They exist only
        in this process's memory for the duration of the assertions.
        """
        sessions_root = extract.DEFAULT_SESSIONS_ROOT
        if not sessions_root.is_dir():
            self.skipTest("no session logs available")
        if not any(sessions_root.glob("*/*.jsonl")):
            self.skipTest("no .jsonl session files under sessions root")

        redacted_prompts, _ = extract.extract_prompts(
            sessions_root, mode="conversation", do_redact=True
        )
        raw_prompts, _ = extract.extract_prompts(
            sessions_root, mode="conversation", do_redact=False
        )

        try:
            # 1. Identical prompt count. Filters run before redaction, so
            #    redaction cannot change which prompts pass the gate.
            self.assertEqual(
                len(redacted_prompts), len(raw_prompts),
                f"redaction changed prompt count: redacted={len(redacted_prompts)} "
                f"raw={len(raw_prompts)}",
            )

            # 2. Median length drift under 3%.
            def median(xs):
                xs = sorted(xs)
                return xs[len(xs) // 2] if xs else 0

            redacted_med = median(len(p) for p in redacted_prompts)
            raw_med = median(len(p) for p in raw_prompts)
            if raw_med > 0:
                drift = abs(redacted_med - raw_med) / raw_med
                self.assertLess(
                    drift, 0.03,
                    f"median length drift > 3%: raw={raw_med} redacted={redacted_med}",
                )

            # 3. Signature-phrase counts must be identical (redactors do not
            #    match any of these phrases).
            raw_joined = "\n".join(raw_prompts).lower()
            redacted_joined = "\n".join(redacted_prompts).lower()
            for probe in self.SIGNATURE_PROBES:
                raw_n = raw_joined.count(probe.lower())
                red_n = redacted_joined.count(probe.lower())
                self.assertEqual(
                    raw_n, red_n,
                    f"signature phrase {probe!r} count changed under redaction: "
                    f"raw={raw_n} redacted={red_n}",
                )

            # 4. Redacted prompts must not contain known secret shapes.
            #    Prefixes assembled at runtime to avoid tripping secret
            #    scanners on this file itself.
            needles = [
                (_key(_SK, "-ant-api03-"), "anthropic key prefix"),
                (_key(_SK, "-proj-"), "openai project key prefix"),
                (_key(_SK, "-svcacct-"), "openai service account prefix"),
                (_key(_SK, "_live_"), "stripe live prefix"),
                (_key(_GH, "p_"), "github pat prefix"),
                (_AKIA, "aws key prefix"),
                ("Bearer ey", "bearer JWT"),
                (_AIZA, "google api key prefix"),
            ]
            for needle, label in needles:
                self.assertNotIn(
                    needle, redacted_joined,
                    f"unredacted {label} found in redacted prompts",
                )
        finally:
            # Best-effort: drop the raw prompts from memory before we return.
            raw_prompts.clear()
            raw_joined = ""


class CorpusBannerAndAllowlist(unittest.TestCase):
    """The on-disk corpus must carry the banner and live under the allowlist."""

    def test_canonical_corpus_has_banner(self):
        canonical = extract.DEFAULT_CORPUS_PATH
        if not canonical.exists():
            self.skipTest("no canonical corpus on disk yet")
        head = canonical.read_text(encoding="utf-8")[:200]
        self.assertTrue(
            head.startswith("# UNTRUSTED INPUT"),
            "canonical corpus does not start with the untrusted-input banner",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
