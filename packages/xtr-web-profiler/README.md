<div align="center">

# xtr-web-profiler

**A development toolbar on every page, and a profile of every request.**

<img alt="python 3.14+" src="https://img.shields.io/badge/python-%E2%89%A5%203.14-3776AB?logo=python&logoColor=white">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

"What did that request actually do?" is the question asked most while building a web
application, and print statements answer it one piece at a time. In development, this package
answers it for every request at once: a toolbar at the foot of each HTML page shows the status,
the time, the memory, the log, the events and the route, and one click opens the request's full
profile — kept for two days and searchable.

- 🧭 **A toolbar on every page.** Drawn into each HTML response as it streams out; nothing to add
  to a template.
- ⏱️ **A timeline.** Every event listener, the application's own handling and the whole request
  on one axis, filterable by duration and by kind.
- 📜 **The request's log.** Every record it made — and only its own, however many requests the
  process serves at once.
- 💥 **The exception, with its frames.** Source around each line, local variables, the chain of
  causes; a link opens the line in your editor.
- 🔁 **Background requests too.** The toolbar lists the `fetch` and `XMLHttpRequest` calls the
  page makes, each linked to its own profile.
- 🧩 **Panels from any library.** A data collector and a template are a new panel; the profiler
  does not need to know it exists.

## Install

```sh
uv run xtr-recipes recipes:add --dev xtr-web-profiler
```

Requires Python 3.14.4+. It installs as a development dependency: production does not install it,
and the recipe lists the bundle for the `dev` environment only.

## Quick start

With [xtr-http-kernel](../xtr-http-kernel) already serving the application through
`setup(app, kernel)`, adding the package is the whole of it. Start the application in `dev`, open
any HTML page, and the toolbar is at its foot:

```console
$ curl -si localhost:8000/books | grep -i debug
x-debug-token: 3f9a1c
x-debug-token-link: http://localhost:8000/_profiler/3f9a1c
```

A response that is not a page — JSON from an API — carries the same two headers: follow
`X-Debug-Token-Link` to its profile, or open `/_profiler/latest`.

## What a profile shows

| Panel | Shows |
|---|---|
| Request | the method, URI, query, parsed body, path parameters, cookies, headers and state of the request; the status and headers of the response; a `curl` command replaying it. Credentials — `Authorization`, `Cookie`, `Set-Cookie`, and every field named like a password, a secret or a token — are kept as `******` |
| Time | the whole request's duration and a timeline of every timed event: the request's section, the application's own handling (`controller`), each event listener |
| Memory | the peak memory of the process serving the request |
| AJAX | the background requests the page made, listed in its toolbar |
| Exception | what handling raised: class, message, chain of causes, and each frame with its source and local variables |
| Logs | every record the request logged, by level, with its context — when [xtr-logging](../xtr-logging) is active. Context entries named like credentials are kept as `******` too |
| Events | the listeners called, how often and for how long, those not called, and the events nobody listened to |
| Routing | the route that answered — name, path template, methods, endpoint, parameters — a redirect's target, and how every route of the application matched the request |
| Config | the Python version, the environment, the active bundles and every xtr package installed |

The profiles themselves are collected by [xtr-http-kernel](../xtr-http-kernel#profiler); this
package shows them.

## The toolbar

The toolbar is drawn into a response only when all of these hold: the toolbar is on, the response
names a profile in `X-Debug-Token`, it is no redirect, its content type is HTML, it is no
attachment, its body is not compressed, and the request was not a background one —
`X-Requested-With: XMLHttpRequest`, or a fetch the browser marks as not loading a document. It
goes in just before the closing `</body>`, found even when a streamed body splits the tag across
two chunks, and `Content-Length` is dropped since the body grew. A page without `</body>` goes out
as it was.

What goes into the page is small: a placeholder and a script. The script fetches the toolbar from
`/_wdt/<token>` — retrying a moment later when the profile has not been written yet, since it is
written once the response has left — and remembers whether you minimised it.

A compressed body cannot be drawn into, and a browser always accepts one. So a request that may get
the toolbar — one accepting HTML, or anything, that is not a background request — reaches the
application without its `Accept-Encoding`: an application compressing its responses, with the
framework's `GZipMiddleware` say, leaves its pages uncompressed in development, and its other
responses compressed.

### Background requests

The page's `fetch` and `XMLHttpRequest` calls are recorded as they go, with their status, their
duration and the profile named by their response, and listed in the toolbar. Calls to the
profiler's own paths are left out — `excluded_ajax_paths` says which. With `ajax_replace`, a
background request whose response names a profile reloads the toolbar with that profile — for a
page that changes what it shows without loading another.

### Redirects

With `intercept_redirects`, a redirect answering a page is replaced by a page saying where it
leads, toolbar included, so the request that redirected — a form post, a sign-in — can be read
before following it.

### Content security policy

The toolbar is an inline script and an inline style. A page sending a policy gets the toolbar's
nonces added to every script and style directive of it, so the toolbar runs and the page's own
rules stay as they were; a page without a policy is left alone. The profiler's own pages are sent
with no policy at all.

## Editor links

A frame of an exception links to the line that ran. By default the link opens the profiler's own
source view, which shows only files under the project directory and never a hidden one. Point it at
your editor instead with `file_link_format`, `{file}` and `{line}` standing for them:

| Editor | `file_link_format` |
|---|---|
| PyCharm | `"pycharm://open?file={file}&line={line}"` |
| VS Code | `"vscode://file/{file}:{line}"` |
| Cursor | `"cursor://file/{file}:{line}"` |

## Writing a panel

A panel is a data collector — registered by any bundle, see
[xtr-http-kernel](../xtr-http-kernel#writing-a-collector) — and a template naming up to four
blocks:

- `toolbar` — the item in the toolbar: call `toolbar_item(name, icon, text, link, status)` with
  the icon and value shown and the text of its popover;
- `menu` — the entry in the profile page's menu;
- `panel` — the panel itself;
- `head` — anything the panel needs in the page's head.

The template is a file of the collector's own package, under `templates/`, named
`"@<import package>/<path>"`; the package needs no template engine of its own:

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

Every block sees `collector` — `collector.name`, and `collector.data`, what the collector kept —
`profile`, `token`, `url(route_name, **parameters)`, `panel_url(panel)`,
`open_file_url(file, line)`, and the CSP nonces `csp_script_nonce` and `csp_style_nonce` for an
inline script or style. Filters: `profiler_dump` shows a value kept through `clone_var` as a
browsable tree; `format_bytes`, `format_ms`, `format_time` and `file_link(file, line)`. A block
naming anything else fails, rather than rendering empty.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what
removing it undoes.

- **Install** — `uv run xtr-recipes recipes:add --dev xtr-web-profiler`: a development dependency,
  never installed in production. [xtr-http-kernel](../xtr-http-kernel) comes with it; install
  [xtr-logging](../xtr-logging) beside it for the log panel. The timeline needs nothing more:
  [xtr-stopwatch](../xtr-stopwatch) comes with the http kernel.
- **Recipe** — `recipes:add` does the *Activate* and *Configure* steps below: it lists
  `WebProfilerBundle` for `dev` and writes `<app>/config/routes/dev/web_profiler.py`. There is no
  environment or ignore line to write; it prints the `setup(app, kernel)` step, which a recipe
  cannot make for you.
- **Activate** — `WebProfilerBundle: {"dev": True}` in `BUNDLES` in `<app>/config/bundles.py`,
  imported from `xtr_web_profiler.bundle`, and `setup(app, kernel)` where the application is
  built, as the http kernel requires.
- **Brings along** — the [http kernel](../xtr-http-kernel)'s bundle, required outright, and with it
  the event dispatcher's. Listing this bundle turns the http kernel's profiler on in the same
  environment.
- **Configure** — `<app>/config/routes/dev/web_profiler.py`, which the recipe writes, serves the
  toolbar under `/_wdt` and the pages under `/_profiler`; it sits in the `dev` folder, so nothing
  of the profiler is routed elsewhere, and deleting it takes the pages down. The bundle's own
  configuration needs nothing; a change goes in `<app>/config/packages/dev/web_profiler.py` — see
  [Configure](#configure).
- **Environment** — nothing.
- **Ignore** — nothing: the profiles are kept under the kernel's cache directory.
- **Remove** — `uv run xtr-recipes recipes:remove xtr-web-profiler` drops the `BUNDLES` entry and
  deletes `<app>/config/routes/dev/web_profiler.py`, unless you edited it, in which case it is moved
  aside.
- **Check** — `debug:bundles` shows `web_profiler` as `listed` and `active` in `dev`; any HTML page
  shows the toolbar; `GET /_profiler/latest` shows the last request's profile.

## Configure

`WebProfilerConfig` is a frozen dataclass buildable with no arguments:

| Field | Default | What it sets |
|---|---|---|
| `toolbar` | `True` | draw the toolbar into HTML pages |
| `ajax_replace` | `False` | reload the toolbar with the profile a background request's response names |
| `intercept_redirects` | `False` | show a redirect answering a page as a page of its own |
| `excluded_ajax_paths` | `"^/(_wdt\|_profiler)"` | a regular expression; background requests to a matching path are not listed |
| `file_link_format` | `None` | how a file and line open in an editor — see [Editor links](#editor-links) |

The constructor refuses an `excluded_ajax_paths` that is no regular expression, and a
`file_link_format` that does not name `{file}`, with `InvalidArgumentError` — also a `ValueError`.

What is profiled — every request, only those asking with a parameter, only failures — is the http
kernel's [profiler configuration](../xtr-http-kernel#profiler).

## Kernel / bundle

```python
# app/config/bundles.py
from xtr_web_profiler.bundle import WebProfilerBundle

BUNDLES = {..., WebProfilerBundle: {"dev": True}}
```

```python
# app/config/packages/dev/web_profiler.py
from xtr_dependency_injection import configure

from xtr_web_profiler.bundle import WebProfilerConfig


@configure
def web_profiler() -> WebProfilerConfig:
    return WebProfilerConfig(
        intercept_redirects=True,
        file_link_format="pycharm://open?file={file}&line={line}",
    )
```

The bundle requires the http kernel's bundle and turns its profiler on. It registers the
controller answering the pages, the template environment, the content security policy handler
and — when the toolbar or redirect interception is on — the toolbar middleware, tagged
`http_kernel.middleware` at priority `1024` (`WEB_DEBUG_TOOLBAR_PRIORITY`): outside the request
lifecycle, whose default is `0`, so it sees the profile's token on the response. An application
raising `HttpKernelConfig.middleware_priority` above it keeps the toolbar off its pages. It
contributes the route resources `web_profiler_wdt` and `web_profiler`. Turned off again through
the http kernel's configuration, the profiler records nothing and every page answers 404. The
zero-config path builds and boots with nothing configured and touches no disk until a request is
profiled.

## Security

**Never list this bundle outside development.** A profile holds every request's headers,
cookies, parameters and state; anybody who can reach `/_profiler` can read them. The recipe lists
it for `dev` only and writes its routes into the `dev` folder, so in any other environment the
pages do not exist, and the bundle warns at build if it finds itself in `prod`. The token naming a
profile is short and not a secret: keeping the pages out of reach is what keeps the profiles
private.

## Errors

Everything this library raises derives from `WebProfilerError`.

| Error | Raised when |
|---|---|
| `InvalidArgumentError` | a `WebProfilerConfig` field holds a value the toolbar would misread; also a `ValueError` |
| `TemplateNotFoundError` | a data collector's tag names a template that does not exist; also a `LookupError` |

## Layout

```
xtr_web_profiler/
├── web_debug_toolbar_middleware.py  draws the toolbar into the pages, links every profile
├── controller/                      the pages: toolbar, profile, search, source view
├── routing/                         the route resources web_profiler_wdt and web_profiler
├── profiler/                        which panels a profile has, and rendering their blocks
├── templating/                      the template environment, its loader and its filters
├── csp/                             the toolbar's nonces under a page's policy
├── templates/                       the pages, the toolbar and the core panels
├── recipe/                          what recipes:add applies
├── exception/                       WebProfilerError, the root of everything this library raises
└── bundle/                          WebProfilerBundle and WebProfilerConfig
```

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-web-profiler`; run the commands below from there.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
