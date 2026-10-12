"""Where a stored deployment's tables are defined, and the column types they use.

Everything here needs the ORM, which the ``orm`` extra brings; the rest of the
package never imports it. The mapping lives in
:mod:`xtr_security_oauth2_server.persistence.mapping` and the column types it
builds the tables from in :mod:`xtr_security_oauth2_server.persistence.type`.

No revision files are shipped: an application generates its own from the tables
the driver builds, so a prefix it chose or a table it turned off is in the
revision it runs.
"""

from __future__ import annotations

__all__: list[str] = []
