"""Tests for shared/unsubscribe_token.py.

Covers: sign/verify round trip, tamper detection (flipped signature), and every
malformed-input shape verify_unsubscribe_token must reject without raising — this
backs an unauthenticated endpoint, so garbage input is the expected case, not
exceptional.
"""

from shared.unsubscribe_token import sign_unsubscribe_token, verify_unsubscribe_token


class TestSignAndVerifyRoundTrip:
    def test_verify_recovers_the_signed_user_id(self):
        token = sign_unsubscribe_token("user-123")

        assert verify_unsubscribe_token(token) == "user-123"

    def test_different_user_ids_produce_different_tokens(self):
        assert sign_unsubscribe_token("user-1") != sign_unsubscribe_token("user-2")

    def test_verify_handles_a_user_id_containing_dots(self):
        # user_id is base64-encoded before being embedded, so a literal "." inside it
        # must not be confused with the token's own "<user_id>.<signature>" separator.
        token = sign_unsubscribe_token("user.with.dots")

        assert verify_unsubscribe_token(token) == "user.with.dots"


class TestVerifyRejectsInvalidTokens:
    def test_rejects_a_tampered_signature(self):
        token = sign_unsubscribe_token("user-123")
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

        assert verify_unsubscribe_token(tampered) is None

    def test_rejects_a_token_signed_for_a_different_user_id(self):
        token = sign_unsubscribe_token("user-1")
        encoded_user_id, signature = token.split(".", 1)
        forged = sign_unsubscribe_token("user-2").split(".", 1)[0] + "." + signature

        assert verify_unsubscribe_token(forged) is None

    def test_rejects_empty_string(self):
        assert verify_unsubscribe_token("") is None

    def test_rejects_a_token_with_no_separator(self):
        assert verify_unsubscribe_token("no-separator-here") is None

    def test_rejects_invalid_base64(self):
        assert verify_unsubscribe_token("not-valid-base64!!!.signature") is None

    def test_rejects_base64_that_decodes_to_invalid_utf8(self):
        # b"\xff\xfe" is not valid UTF-8 — the user_id segment must fail to decode.
        invalid_utf8_b64 = "//4"
        assert verify_unsubscribe_token(f"{invalid_utf8_b64}.signature") is None

    def test_rejects_a_non_ascii_signature_without_raising(self):
        # hmac.compare_digest raises TypeError (not ValueError) on a non-ASCII str
        # operand — a naive except ValueError alone would let this crash the caller
        # (an unauthenticated endpoint) instead of returning None.
        encoded_user_id = sign_unsubscribe_token("user-123").split(".", 1)[0]
        assert verify_unsubscribe_token(f"{encoded_user_id}.é") is None
