#!/usr/bin/env python3
import unittest
from peer_model import (
    PROTOCOL_VERSION,
    assert_bot_matches_lab,
    assert_peer_pair,
    assert_remote_health,
    format_chat_outbound,
    format_chat_reply,
    is_addressed_to,
    is_fast_ping,
    monotonic_warning,
    parse_message_id,
    resolve_me,
    should_alpha_free_respond,
    validate_nonempty,
)


class TestNoSwapInvariants(unittest.TestCase):
    def test_pair_ok(self):
        self.assertIsNone(assert_peer_pair("alpha", "beta"))
        self.assertIsNone(assert_peer_pair("beta", "alpha"))

    def test_pair_rejects_self(self):
        self.assertTrue(assert_peer_pair("alpha", "alpha").startswith("error"))

    def test_pair_rejects_wrong_remote(self):
        # alpha must not treat alpha as remote of alpha already covered;
        # unknown remote
        self.assertTrue(assert_peer_pair("alpha", "gamma").startswith("error"))

    def test_bot_match(self):
        self.assertIsNone(assert_bot_matches_lab("alpha", "erynoa_alpha_hermes_bot"))
        self.assertIsNone(assert_bot_matches_lab("beta", "erynoa_beta_hermes_bot"))
        err = assert_bot_matches_lab("alpha", "erynoa_beta_hermes_bot")
        self.assertTrue(err.startswith("error: identity mismatch"))

    def test_remote_health(self):
        self.assertIsNone(assert_remote_health("alpha", "beta"))
        self.assertTrue(assert_remote_health("alpha", "alpha").startswith("error"))
        self.assertTrue(assert_remote_health("alpha", "gamma").startswith("error"))

    def test_resolve_symmetric(self):
        a, b = resolve_me("alpha"), resolve_me("beta")
        self.assertEqual(a["remote_id"], "beta")
        self.assertEqual(b["remote_id"], "alpha")
        self.assertNotEqual(a["bot"], b["bot"])


class TestAddressRule1(unittest.TestCase):
    def test_mentions(self):
        self.assertTrue(is_addressed_to("@erynoa_alpha_hermes_bot hi", "alpha"))
        self.assertFalse(is_addressed_to("@erynoa_alpha_hermes_bot hi", "beta"))
        self.assertTrue(is_addressed_to("frag beta", "beta"))
        self.assertFalse(is_addressed_to("frag beta", "alpha"))

    def test_plain_text_addresses_neither(self):
        # T1: plain human text — no alias hit for either lab
        self.assertFalse(is_addressed_to("wie geht es euch heute", "alpha"))
        self.assertFalse(is_addressed_to("wie geht es euch heute", "beta"))

    def test_both_mentioned(self):
        # T4: both bots mentioned — both are addressed
        both = "@erynoa_alpha_hermes_bot @erynoa_beta_hermes_bot status bitte"
        self.assertTrue(is_addressed_to(both, "alpha"))
        self.assertTrue(is_addressed_to(both, "beta"))

    def test_reply_to_is_self(self):
        # T5/T6: reply-to entity addresses the replied-to bot regardless of text
        self.assertTrue(is_addressed_to("ok", "beta", reply_to_is_self=True))
        self.assertFalse(is_addressed_to("ok", "beta", reply_to_is_self=False))

    def test_explicit_mentions_param(self):
        self.assertTrue(
            is_addressed_to("kurz melden", "alpha", explicit_mentions=["@erynoa_alpha_hermes_bot"])
        )
        self.assertFalse(
            is_addressed_to("kurz melden", "alpha", explicit_mentions=["@erynoa_beta_hermes_bot"])
        )


class TestFreeRespondLaw(unittest.TestCase):
    """Protocol §4 — should_alpha_free_respond truth-table rows."""

    def test_t1_plain_text(self):
        self.assertTrue(should_alpha_free_respond("wie geht's euch"))

    def test_prose_names_are_not_addresses(self):
        # "frag beta online" is an instruction TO alpha, not an address of beta
        self.assertTrue(should_alpha_free_respond("frag beta ob er online ist"))

    def test_t3_exclusive_beta_mention(self):
        self.assertFalse(
            should_alpha_free_respond("mach du das", ["@erynoa_beta_hermes_bot"])
        )

    def test_t4_both_mentioned(self):
        self.assertTrue(
            should_alpha_free_respond(
                "beide bitte", ["@erynoa_alpha_hermes_bot", "@erynoa_beta_hermes_bot"]
            )
        )

    def test_t6_reply_to_beta(self):
        self.assertFalse(
            should_alpha_free_respond("und du?", reply_to_bot="erynoa_beta_hermes_bot")
        )

    def test_t5_reply_to_alpha(self):
        self.assertTrue(
            should_alpha_free_respond("und du?", reply_to_bot="erynoa_alpha_hermes_bot")
        )

    def test_bot_author_never_triggers(self):
        self.assertFalse(should_alpha_free_respond("hallo", author_is_human=False))

    def test_wrong_chat(self):
        self.assertFalse(should_alpha_free_respond("hallo", chat_id="-123"))

    def test_gamma_proof_other_bot_exclusive(self):
        # future γ: exclusive mention of any other lab bot silences alpha
        self.assertFalse(
            should_alpha_free_respond("nur du", ["@erynoa_gamma_hermes_bot"])
        )


class TestMessageIdHelpers(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_message_id("posted chat=-5535276728 message_id=161 as=alpha"), 161)
        self.assertIsNone(parse_message_id("error: telegram post failed"))

    def test_monotonic(self):
        self.assertIsNone(monotonic_warning(160, 161))
        self.assertIsNotNone(monotonic_warning(161, 160))
        self.assertIsNotNone(monotonic_warning(161, 161))
        self.assertIsNone(monotonic_warning(None, 161))

    def test_protocol_version(self):
        self.assertRegex(PROTOCOL_VERSION, r"^\d+\.\d+\.\d+$")


class TestChat(unittest.TestCase):
    def test_outbound_targets_peer_only(self):
        line = format_chat_outbound("hi", peer_bot="erynoa_beta_hermes_bot", peer_name="beta")
        self.assertIn("@erynoa_beta_hermes_bot", line)
        self.assertNotIn("alpha_hermes", line)
        self.assertNotIn("PEER", line)

    def test_reply_clean(self):
        self.assertEqual(format_chat_reply("α: pong"), "pong")

    def test_ping(self):
        self.assertTrue(is_fast_ping("online?"))
        self.assertIsNone(validate_nonempty("x"))



class TestNoLabPrefix(unittest.TestCase):
    def test_strips_greek_and_name(self):
        from peer_model import clean_chat_text, format_chat_reply, fast_pong_text
        self.assertEqual(format_chat_reply("α: hi there"), "hi there")
        self.assertEqual(format_chat_reply("β: online"), "online")
        self.assertEqual(format_chat_reply("Alpha: alles gut"), "alles gut")
        self.assertEqual(format_chat_reply("beta — jo"), "jo")
        self.assertNotIn("alpha", fast_pong_text("alpha").lower())
        self.assertNotIn("beta", fast_pong_text("beta").lower())
        self.assertNotIn("α", format_chat_reply("α pong"))
        self.assertEqual(clean_chat_text("[beta] hey"), "hey")


if __name__ == "__main__":
    unittest.main(verbosity=2)
