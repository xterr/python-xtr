"""The three places a deployment's clients and credentials can live."""

from __future__ import annotations

from tests.support.custom_stores import (
    ApplicationAccessTokenStore,
    ApplicationAuthorizationCodeStore,
    ApplicationClientStore,
    ApplicationCredentialsRevoker,
    ApplicationDeviceCodeStore,
    ApplicationRefreshTokenStore,
)
from xtr_security_oauth2_server.bundle.persistence_configs import (
    CustomPersistenceConfig,
    InMemoryPersistenceConfig,
    OrmPersistenceConfig,
)


def test_the_stored_persistence_defaults_to_the_default_connection() -> None:
    stored = OrmPersistenceConfig()

    assert stored.connection == "default"
    assert stored.table_prefix == "oauth2_"


def test_the_in_process_persistence_takes_no_options() -> None:
    assert InMemoryPersistenceConfig() == InMemoryPersistenceConfig()


def test_the_application_persistence_names_all_six_stores() -> None:
    # Five halves of one store and the sixth that withdraws everything at
    # once: a deployment answering for some of them would have two stores
    # disagreeing about the same token.
    # Named as any class: what the bundle checks is that each is a service
    # this container holds, which is its ``process`` hook's business.
    named = CustomPersistenceConfig(
        access_token_manager=ApplicationAccessTokenStore,
        authorization_code_manager=ApplicationAuthorizationCodeStore,
        client_manager=ApplicationClientStore,
        refresh_token_manager=ApplicationRefreshTokenStore,
        device_code_manager=ApplicationDeviceCodeStore,
        credentials_revoker=ApplicationCredentialsRevoker,
    )

    assert named.client_manager is ApplicationClientStore
