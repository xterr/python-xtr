"""The keys the security flow parks on a request, and their two spellings."""

from __future__ import annotations

from xtr_security_http.security_request_attributes import SecurityRequestAttributes


def test_the_application_facing_keys_carry_the_documented_spelling() -> None:
    assert SecurityRequestAttributes.ACCESS_DENIED_ERROR == "_security.403_error"
    assert SecurityRequestAttributes.AUTHENTICATION_ERROR == "_security.last_error"
    assert SecurityRequestAttributes.LAST_USERNAME == "_security.last_username"
    assert SecurityRequestAttributes.UNSUPPORTED_REASONS == "_security.unsupported_reasons"
    assert (
        SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE
        == "_security.re_authentication_attribute"
    )


def test_the_target_path_key_is_composed_with_the_firewall_name() -> None:
    key = SecurityRequestAttributes.TARGET_PATH.format(firewall="main")

    assert key == "_security.main.target_path"


def test_the_flow_internal_keys_carry_the_prefixed_spelling() -> None:
    assert SecurityRequestAttributes.SECURITY_STATE == "_xtr_security_"
    assert SecurityRequestAttributes.AUTHENTICATORS == "_xtr_security_authenticators"
    assert (
        SecurityRequestAttributes.SKIPPED_AUTHENTICATORS == "_xtr_security_skipped_authenticators"
    )
    assert (
        SecurityRequestAttributes.ACCESS_CONTROL_ATTRIBUTES
        == "_xtr_security_access_control_attributes"
    )
    assert SecurityRequestAttributes.FIREWALL_RUN == "_xtr_security_firewall_run"
    assert SecurityRequestAttributes.SESSION == "_xtr_security_session"
    assert (
        SecurityRequestAttributes.PRE_AUTHENTICATED_USERNAME
        == "_xtr_security_pre_authenticated_username"
    )
    assert SecurityRequestAttributes.LOGIN_LINK_PARAMETERS == "_xtr_security_login_link_parameters"
    assert SecurityRequestAttributes.REMEMBER_ME_COOKIE == "_xtr_security_remember_me_cookie"


def test_no_two_keys_are_the_same() -> None:
    keys = {
        SecurityRequestAttributes.ACCESS_DENIED_ERROR,
        SecurityRequestAttributes.AUTHENTICATION_ERROR,
        SecurityRequestAttributes.LAST_USERNAME,
        SecurityRequestAttributes.UNSUPPORTED_REASONS,
        SecurityRequestAttributes.RE_AUTHENTICATION_ATTRIBUTE,
        SecurityRequestAttributes.TARGET_PATH,
        SecurityRequestAttributes.SECURITY_STATE,
        SecurityRequestAttributes.AUTHENTICATORS,
        SecurityRequestAttributes.SKIPPED_AUTHENTICATORS,
        SecurityRequestAttributes.ACCESS_CONTROL_ATTRIBUTES,
        SecurityRequestAttributes.FIREWALL_RUN,
        SecurityRequestAttributes.SESSION,
        SecurityRequestAttributes.PRE_AUTHENTICATED_USERNAME,
        SecurityRequestAttributes.LOGIN_LINK_PARAMETERS,
        SecurityRequestAttributes.REMEMBER_ME_COOKIE,
    }

    assert len(keys) == 15
