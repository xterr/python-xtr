from __future__ import annotations

from xtr_http_client.internal.mock_head import (
    header_lines,
    response_header_lines,
    scripted_message,
)


def test_an_answer_the_script_says_nothing_about_is_an_empty_200() -> None:
    message = scripted_message({}, None)

    assert message.get_status_code() == 200
    assert message.get_reason_phrase() == "OK"
    assert message.get_protocol_version() == "1.1"
    assert message.get_headers() == {}


def test_the_status_is_the_one_the_script_claims() -> None:
    assert scripted_message({"http_code": 404}, None).get_status_code() == 404


def test_a_status_that_is_not_one_leaves_the_status_as_it_was() -> None:
    assert scripted_message({"http_code": "404"}, None).get_status_code() == 200
    assert scripted_message({"http_code": True}, None).get_status_code() == 200


def test_a_status_line_says_the_version_the_status_and_the_reason() -> None:
    message = scripted_message({"response_headers": ["HTTP/2 404 Nope", "X-Foo: bar"]}, None)

    assert message.get_protocol_version() == "2"
    assert message.get_status_code() == 404
    assert message.get_reason_phrase() == "Nope"
    assert message.get_header("x-foo") == ["bar"]


def test_a_status_line_with_no_reason_takes_the_one_recommended_for_the_status() -> None:
    message = scripted_message({"response_headers": ["HTTP/1.1 201"]}, None)

    assert message.get_reason_phrase() == "Created"


def test_a_status_line_overrides_the_status_the_script_claimed() -> None:
    message = scripted_message({"http_code": 500, "response_headers": ["HTTP/1.1 204 "]}, None)

    assert message.get_status_code() == 204
    assert message.get_reason_phrase() == ""


def test_a_hop_answers_for_itself_and_not_for_the_one_before_it() -> None:
    message = scripted_message(
        {
            "response_headers": [
                "HTTP/1.1 103 ",
                "Link: </style.css>; rel=preload",
                "HTTP/1.1 200 ",
                "Date: foo",
            ]
        },
        None,
    )

    assert message.get_status_code() == 200
    assert not message.has_header("link")
    assert message.get_header_line("date") == "foo"


def test_a_header_name_is_kept_in_the_case_it_was_first_written_in() -> None:
    message = scripted_message({"response_headers": ["Set-Cookie: a=1", "set-cookie: b=2"]}, None)

    assert message.get_headers() == {"Set-Cookie": ["a=1", "b=2"]}


def test_a_line_that_names_no_header_is_not_one() -> None:
    assert scripted_message({"response_headers": ["nonsense"]}, None).get_headers() == {}


def test_the_content_length_is_made_to_say_what_the_body_really_is() -> None:
    message = scripted_message({"response_headers": ["content-length: 4"]}, 7)

    assert message.get_header("Content-Length") == ["7"]
    assert list(message.get_headers()) == ["content-length"]


def test_a_body_of_unknown_length_leaves_the_length_as_the_script_claimed() -> None:
    message = scripted_message({"response_headers": {"content-length": "1000"}}, None)

    assert message.get_header("content-length") == ["1000"]


def test_headers_can_be_named_rather_than_written_out_as_lines() -> None:
    message = scripted_message(
        {"response_headers": {"X-Foo": ["a", "b"], "X-Bar": "c", "X-Count": 2}},
        None,
    )

    assert message.get_header("x-foo") == ["a", "b"]
    assert message.get_header("x-bar") == ["c"]
    assert message.get_header("x-count") == ["2"]


def test_one_header_can_be_written_as_one_line() -> None:
    assert response_header_lines("X-Foo: bar") == ["X-Foo: bar"]


def test_nothing_said_about_the_headers_is_no_headers() -> None:
    assert response_header_lines(None) == []


def test_the_lines_of_a_message_are_its_status_line_then_its_headers() -> None:
    message = scripted_message({"http_code": 201, "response_headers": {"X-Foo": "bar"}}, 3)

    assert header_lines(message) == ["HTTP/1.1 201 Created", "X-Foo: bar", "Content-Length: 3"]
