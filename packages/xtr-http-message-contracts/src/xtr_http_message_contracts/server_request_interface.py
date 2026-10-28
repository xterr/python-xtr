"""A request as it arrived, with everything the server learned alongside it."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable

from .request_interface import RequestInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["ServerRequestInterface"]


@runtime_checkable
class ServerRequestInterface(RequestInterface, Protocol):
    """An incoming, server-side request.

    On top of what every request carries — a protocol version, a method, a
    URI, headers and a body — this one gathers everything that reached the
    application with it:

    - the parameters of the environment it arrived in;
    - the cookies the client sent;
    - the query string, parsed;
    - the files that came with it, if any;
    - the body, parsed into parameters.

    The environment parameters are the state the request arrived in and
    nothing may change them, which is why there is no method to. The rest can
    all be rebuilt from the environment or from the body — a body may need
    parsing differently once its content type is known, for one — so each of
    those does have a method.

    A request is also worth annotating as it is handled: a path matched into
    named parameters, a cookie decrypted, an authorization header resolved to
    a user. Those findings go in the attributes.

    Requests are immutable. Every ``with_*`` method keeps the instance it was
    called on as it was and returns one carrying the change. A request built
    over a connection materialises its body side lazily, and its sync getters
    answer what materialisation has yielded so far.
    """

    def get_server_params(self) -> Mapping[str, object]:
        """Return the parameters of the environment the request arrived in.

        Where they came from is nobody's business but the implementation's:
        they need not describe a server process at all.

        Returns:
            The environment parameters, each under the name the environment
            gave it.
        """
        ...

    def get_cookie_params(self) -> Mapping[str, str]:
        """Return the cookies the client sent.

        Returns:
            Each cookie name mapped to its value.
        """
        ...

    def with_cookie_params(self, cookies: Mapping[str, str]) -> Self:
        """Return an instance carrying ``cookies``.

        The cookies need not be the ones that arrived; they are usually
        supplied when the request is built.

        Neither the ``Cookie`` header of the new instance nor its environment
        parameters change with them.

        Args:
            cookies: Each cookie name mapped to its value.

        Returns:
            A new instance; this one is left as it was.
        """
        ...

    def get_query_params(self) -> Mapping[str, object]:
        """Return the query string, parsed into parameters.

        These may have drifted from the URI and from the environment
        parameters, since nothing keeps the three in step. To be sure of
        reading what arrived, parse ``get_uri().get_query()``, or the query
        string among the environment parameters, instead.

        Returns:
            Each parameter name mapped to its value: a string, or a nested
            structure where the name repeats or nests.
        """
        ...

    def with_query_params(self, query: Mapping[str, object]) -> Self:
        """Return an instance carrying ``query``.

        The parameters should not change over the course of the request. They
        may be supplied when the request is built, or derived from something
        else such as the URI — and where they are parsed out of the URI, how
        a repeated name and how a nested name come out must match what
        :meth:`get_query_params` promises.

        Neither the URI the request holds nor its environment parameters
        change with them.

        Args:
            query: Each parameter name mapped to its value.

        Returns:
            A new instance; this one is left as it was.
        """
        ...

    def get_uploaded_files(self) -> Mapping[str, object]:
        """Return the files that came with the request.

        The files are arranged in a tree that follows the names of the fields
        they were submitted under, every leaf of it an
        :class:`~xtr_http_message_contracts.uploaded_file_interface.UploadedFileInterface`.

        They may have been gathered from the environment or from the body when
        the request was built, or supplied through
        :meth:`with_uploaded_files`.

        Returns:
            The tree of uploaded files. No files at all gives an empty
            mapping.
        """
        ...

    def with_uploaded_files(self, uploaded_files: Mapping[str, object]) -> Self:
        """Return an instance carrying ``uploaded_files``.

        Args:
            uploaded_files: A tree of uploaded files, shaped as
                :meth:`get_uploaded_files` describes.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            ValueError: When the tree is not shaped that way.
        """
        ...

    def get_parsed_body(self) -> object | None:
        """Return the parameters found in the body of the request.

        A ``POST`` whose content type is form-encoded or a multipart form must
        answer with the submitted form fields. A request built over a
        connection answers them once its body has been read, or once it was
        handed over with its body already materialised.

        Anything else may answer with whatever parsing the body yielded.
        Parsing yields structure, so what comes back is a mapping or an object
        — never a scalar.

        Returns:
            The parsed body parameters, or ``None`` when the request has no
            body to parse.
        """
        ...

    def with_parsed_body(self, data: object | None) -> Self:
        """Return an instance carrying ``data`` as its body parameters.

        The parameters may be supplied when the request is built. Where the
        content type is form-encoded or a multipart form and the method is
        ``POST``, this method is for the submitted form fields and nothing
        else.

        The data need not have come from a form, but it must be what parsing
        the body yielded. Parsing yields structure, so only a mapping or an
        object is accepted — or ``None`` when there was nothing to parse.

        A request whose content was negotiated to be a JSON payload, for
        instance, can be given the deserialised payload this way.

        Args:
            data: The parsed body parameters, or ``None``.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            ValueError: When the data is of a kind that cannot be body
                parameters.
        """
        ...

    def get_attributes(self) -> Mapping[str, object]:
        """Return what was derived from the request while handling it.

        Anything at all: the named parameters a path matched, the plaintext of
        a cookie, the result of parsing a body that was not a form. They
        belong to the application and to the request, and may change over its
        course.

        Returns:
            Each attribute name mapped to its value.
        """
        ...

    def get_attribute(self, name: str, default: object | None = None) -> object | None:
        """Return one of the attributes :meth:`get_attributes` describes.

        Being able to name what an absent attribute should read as is why
        there is no method for asking whether one is there.

        Args:
            name: The attribute name.
            default: What to answer with when the request carries no such
                attribute.

        Returns:
            The value under ``name``, or ``default``.
        """
        ...

    def with_attribute(self, name: str, value: object) -> Self:
        """Return an instance carrying one more of the attributes :meth:`get_attributes` describes.

        Args:
            name: The attribute name.
            value: The value to record under it.

        Returns:
            A new instance; this one is left as it was.
        """
        ...

    def without_attribute(self, name: str) -> Self:
        """Return an instance with the ``name`` attribute gone.

        Args:
            name: The attribute name.

        Returns:
            A new instance; this one is left as it was.
        """
        ...
