from __future__ import annotations

import pytest

from xtr_storage.config import Config
from xtr_storage.exception import InvalidArgumentError, InvalidVisibilityError
from xtr_storage.identical_path_policy import IdenticalPathPolicy
from xtr_storage.visibility import Visibility


def test_an_option_nobody_set_answers_none() -> None:
    assert Config().get("missing") is None


def test_an_option_nobody_set_answers_the_default_given() -> None:
    assert Config().get("missing", "fallback") == "fallback"


def test_an_option_that_was_set_is_returned() -> None:
    assert Config({"a": 1}).get("a") == 1


def test_the_options_given_are_copied() -> None:
    options: dict[str, object] = {"a": 1}
    config = Config(options)

    options["a"] = 2

    assert config.get("a") == 1


def test_extend_lets_the_new_value_win() -> None:
    assert Config({"a": 1}).extend({"a": 2}).get("a") == 2


def test_extend_keeps_options_the_new_mapping_does_not_name() -> None:
    assert Config({"a": 1, "b": 2}).extend({"a": 3}).get("b") == 2


def test_extend_leaves_the_configuration_it_was_called_on_alone() -> None:
    config = Config({"a": 1})

    _ = config.extend({"a": 2})

    assert config.get("a") == 1


def test_with_defaults_keeps_a_value_that_is_already_there() -> None:
    assert Config({"a": 1}).with_defaults({"a": 3}).get("a") == 1


def test_with_defaults_fills_in_a_value_nobody_set() -> None:
    assert Config({"a": 1}).with_defaults({"b": 4}).get("b") == 4


def test_with_setting_returns_a_configuration_carrying_the_new_value() -> None:
    assert Config().with_setting("a", 1).get("a") == 1


def test_with_setting_leaves_the_configuration_it_was_called_on_alone() -> None:
    config = Config()

    _ = config.with_setting("a", 1)

    assert config.get("a") is None


def test_without_settings_drops_the_options_it_names() -> None:
    assert Config({"a": 1, "b": 2}).without_settings("a").to_dict() == {"b": 2}


def test_without_settings_drops_several_at_once() -> None:
    assert Config({"a": 1, "b": 2, "c": 3}).without_settings("a", "c").to_dict() == {"b": 2}


def test_without_settings_ignores_an_option_that_was_never_set() -> None:
    assert Config({"a": 1}).without_settings("nothing").to_dict() == {"a": 1}


def test_a_dropped_option_is_gone_rather_than_none() -> None:
    assert "a" not in Config({"a": 1}).without_settings("a").to_dict()


def test_to_dict_hands_out_a_copy() -> None:
    config = Config({"a": 1})

    config.to_dict()["a"] = 2

    assert config.get("a") == 1


def test_visibility_option_reads_the_string_form() -> None:
    config = Config({Config.VISIBILITY: "public"})

    assert config.visibility_option(Config.VISIBILITY) is Visibility.PUBLIC


def test_visibility_option_reads_a_member() -> None:
    config = Config({Config.VISIBILITY: Visibility.PRIVATE})

    assert config.visibility_option(Config.VISIBILITY) is Visibility.PRIVATE


def test_visibility_option_answers_none_when_nobody_asked() -> None:
    assert Config().visibility_option(Config.VISIBILITY) is None


def test_visibility_option_refuses_a_value_that_is_not_text() -> None:
    config = Config({Config.VISIBILITY: 1})

    with pytest.raises(InvalidArgumentError, match="visibility"):
        _ = config.visibility_option(Config.VISIBILITY)


def test_visibility_option_refuses_text_naming_no_visibility() -> None:
    config = Config({Config.VISIBILITY: "world"})

    with pytest.raises(InvalidVisibilityError):
        _ = config.visibility_option(Config.VISIBILITY)


def test_bool_option_answers_the_default_when_nobody_set_it() -> None:
    assert Config().bool_option(Config.RETAIN_VISIBILITY, default=True) is True


def test_bool_option_reads_a_flag_that_was_set() -> None:
    config = Config({Config.RETAIN_VISIBILITY: False})

    assert config.bool_option(Config.RETAIN_VISIBILITY, default=True) is False


def test_bool_option_refuses_a_value_that_is_neither_true_nor_false() -> None:
    config = Config({Config.RETAIN_VISIBILITY: "yes"})

    with pytest.raises(InvalidArgumentError, match="true or false"):
        _ = config.bool_option(Config.RETAIN_VISIBILITY, default=True)


def test_identical_path_policy_tries_the_operation_when_nobody_chose() -> None:
    assert Config().identical_path_policy(Config.COPY_IDENTICAL_PATH) is IdenticalPathPolicy.TRY


def test_identical_path_policy_reads_the_string_form() -> None:
    config = Config({Config.MOVE_IDENTICAL_PATH: "fail"})

    assert config.identical_path_policy(Config.MOVE_IDENTICAL_PATH) is IdenticalPathPolicy.FAIL


def test_identical_path_policy_reads_a_member() -> None:
    config = Config({Config.COPY_IDENTICAL_PATH: IdenticalPathPolicy.IGNORE})

    assert config.identical_path_policy(Config.COPY_IDENTICAL_PATH) is IdenticalPathPolicy.IGNORE


def test_identical_path_policy_refuses_text_naming_no_policy() -> None:
    config = Config({Config.COPY_IDENTICAL_PATH: "overwrite"})

    with pytest.raises(InvalidArgumentError, match="try, fail, ignore"):
        _ = config.identical_path_policy(Config.COPY_IDENTICAL_PATH)


def test_identical_path_policy_refuses_a_value_that_is_not_text() -> None:
    config = Config({Config.COPY_IDENTICAL_PATH: 1})

    with pytest.raises(InvalidArgumentError, match="policy"):
        _ = config.identical_path_policy(Config.COPY_IDENTICAL_PATH)


def test_str_option_answers_the_default_when_nobody_set_it() -> None:
    assert Config().str_option(Config.CHECKSUM_ALGORITHM, "md5") == "md5"


def test_str_option_reads_text_that_was_set() -> None:
    config = Config({Config.CHECKSUM_ALGORITHM: "sha256"})

    assert config.str_option(Config.CHECKSUM_ALGORITHM, "md5") == "sha256"


def test_str_option_refuses_a_value_that_is_not_text() -> None:
    config = Config({Config.CHECKSUM_ALGORITHM: 256})

    with pytest.raises(InvalidArgumentError, match="text"):
        _ = config.str_option(Config.CHECKSUM_ALGORITHM, "md5")


def test_two_configurations_holding_the_same_options_are_equal() -> None:
    assert Config({"a": 1}) == Config({"a": 1})


def test_two_configurations_holding_different_options_are_not_equal() -> None:
    assert Config({"a": 1}) != Config({"a": 2})


def test_a_configuration_is_not_equal_to_a_plain_mapping() -> None:
    assert Config({"a": 1}) != {"a": 1}


def test_the_repr_names_the_options_in_force() -> None:
    assert repr(Config({"a": 1})) == "Config({'a': 1})"


def test_the_option_names_are_the_ones_a_configuration_file_writes() -> None:
    assert (
        Config.VISIBILITY,
        Config.DIRECTORY_VISIBILITY,
        Config.RETAIN_VISIBILITY,
        Config.MOVE_IDENTICAL_PATH,
        Config.COPY_IDENTICAL_PATH,
        Config.CHECKSUM_ALGORITHM,
        Config.PUBLIC_URL,
        Config.ALLOW_RELATIVE_PATH_TRAVERSAL,
    ) == (
        "visibility",
        "directory_visibility",
        "retain_visibility",
        "move_identical_path",
        "copy_identical_path",
        "checksum_algorithm",
        "public_url",
        "allow_relative_path_traversal",
    )
