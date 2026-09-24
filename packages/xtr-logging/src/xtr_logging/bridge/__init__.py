"""Adapters between this library and something that logs its own way.

Kept apart from the core because everything there stands on its own: a
:class:`~xtr_logging.logger.Logger` needs no third party to work. A bridge
does — it speaks to the standard library's :mod:`logging`, or to whatever
else an application already logs through — so it lives here, reached only
when that other side is actually in play.
"""
