---
name: xtr-web-profiler
description: How to use xtr-web-profiler, the development toolbar drawn into every HTML page and the pages showing each request's profile (request, timeline, memory, logs, events, routing, exception, background requests). Use when adding the toolbar or the profiler to an application in dev, reading a request's profile from X-Debug-Token or /_profiler, writing a panel for a library's own data collector, pointing frame links at an editor, intercepting redirects, a toolbar missing from a page, or WebProfilerBundle being added to an application on xtr-dependency-injection.
---

# xtr-web-profiler

In `dev`, every HTML page gets a toolbar at its foot, and every request a profile under
`/_profiler/<token>`. The profiles are collected by the http kernel's profiler; this package draws
them and the panels that show them.

## Quick reference

- Add it: `uv run xtr-recipes recipes:add --dev xtr-web-profiler` — lists `WebProfilerBundle` for
  `dev` and writes `config/routes/dev/web_profiler.py`.
- Find a profile: the response's `X-Debug-Token` names it, `X-Debug-Token-Link` is its page;
  `/_profiler/latest` is the newest, `/_profiler/` the search.
- Configure: `WebProfilerConfig(toolbar=True, ajax_replace=False, intercept_redirects=False,
  excluded_ajax_paths="^/(_wdt|_profiler)", file_link_format=None)`, from
  `xtr_web_profiler.bundle`.
- What is profiled is the http kernel's business: `HttpKernelConfig.profiler` — see the
  `xtr-http-kernel` skill.
- Template names: `"@<import package>/<path under templates/>"`.

## Open frame links in the editor

```python
# app/config/packages/dev/web_profiler.py
from xtr_dependency_injection import configure

from xtr_web_profiler.bundle import WebProfilerConfig


@configure
def web_profiler() -> WebProfilerConfig:
    return WebProfilerConfig(file_link_format="pycharm://open?file={file}&line={line}")
```

`{file}` and `{line}` are the placeholders — never `%f`, which the container reads as a parameter.

## Write a panel for a collector

Register the collector in the library's bundle with the template it is shown with (see the
`xtr-http-kernel` skill for the collector itself), and ship the template under the library's
`templates/` folder:

```jinja
{# src/xtr_orm/templates/collector/orm.html.j2 #}
{% block toolbar %}
  {% from "@xtr_web_profiler/profiler/toolbar_item.html.j2" import toolbar_item %}
  {% set icon %}<span class="xtr-toolbar-value">{{ collector.data.count }} queries</span>{% endset %}
  {% set text %}<b>Time</b> {{ collector.data.duration_ms | format_ms }}{% endset %}
  {{ toolbar_item(collector.name, icon, text, link=panel_url(collector.name)) }}
{% endblock %}
{% block menu %}<span class="xtr-label">Database</span>{% endblock %}
{% block panel %}
  {% for query in collector.data.queries %}<pre>{{ query.sql }}</pre>{% endfor %}
{% endblock %}
```

- Each block is rendered on its own: do not `extends`, and import inside the block.
- A block sees `collector` (`.name`, `.data`), `profile`, `token`, `url`, `panel_url`,
  `open_file_url`, `csp_script_nonce`, `csp_style_nonce`; any other name fails.
- `toolbar_item(name, icon, text, link=None, status="normal")`, `status` one of `normal`, `green`,
  `yellow`, `red`.
- Filters: `profiler_dump` (a `clone_var` tree), `format_bytes`, `format_ms`, `format_time`,
  `file_link(file, line)`.
- An inline `<script>` or `<style>` carries `nonce="{{ csp_script_nonce }}"` /
  `nonce="{{ csp_style_nonce }}"`.

## Read a profile in a test

```python
from xtr_http_kernel.profiler import FileProfilerStorage

response = await client.get("/books")
profile = FileProfilerStorage(folder).read(response.headers["x-debug-token"])
assert profile is not None
assert profile.get_collector("router")["name"] == "show_book"
```

Point `HttpKernelConfig.profiler.storage_path` at the test's folder to read its profiles.

## Testing

- Every page is served through the http kernel, so drive the application with
  `httpx.ASGITransport` inside its lifespan, as the `xtr-http-kernel` skill shows.
- A test environment other than `dev` has no profiler routes: the response then says so in
  `X-Debug-Error`, and no toolbar is drawn.
- `assert_zero_config(WebProfilerBundle)` from `xtr_dependency_injection.testing` holds.

## Use in an application

1. `uv run xtr-recipes recipes:add --dev xtr-web-profiler`.
2. The recipe lists `WebProfilerBundle: {"dev": True}` in `config/bundles.py` and writes
   `config/routes/dev/web_profiler.py`, serving `/_wdt` and `/_profiler`.
3. Call `setup(app, kernel)` where the application is built, if it does not already.
4. Install `xtr-logging` beside it for the log panel.
5. Check: `debug:bundles` shows `web_profiler` active in `dev`; an HTML page shows the toolbar;
   `GET /_profiler/latest` answers.
6. Remove: `uv run xtr-recipes recipes:remove xtr-web-profiler`.

## Errors

| Error | Raised when |
|---|---|
| `InvalidArgumentError` | `excluded_ajax_paths` is no regular expression, or `file_link_format` lacks `{file}`; also a `ValueError` |
| `TemplateNotFoundError` | a collector's tag names a template that does not exist; also a `LookupError` |

A toolbar missing from a page: the response is not HTML, is an attachment, is compressed, is a
redirect, carries no `X-Debug-Token` (the path is excluded from profiling, or profiling is off), or
the request was a background one.

## Do not

- Do not list `WebProfilerBundle` outside `dev`, and do not move its routes file out of
  `config/routes/dev/`: a profile holds every request's headers, cookies and state.
- Do not install it as a regular dependency; it is `--dev`.
- Do not `extends` in a collector template, nor use `|safe` on collector data.
- Do not raise `HttpKernelConfig.middleware_priority` above `1024`: the toolbar middleware must
  stay outside the lifecycle to see the profile's token.
- Do not write `%f`/`%l` in `file_link_format`.
