# Protect a web application

A firewall claims a slice of the request space and says who a request comes
from. The access rules then say what that caller can reach. One configuration
file holds the firewalls, the user providers and the rules.

## Before you start

- Make a web application with the steps in
  [Create an application](../setup/new-application.md). The `--webapp` template
  installs `xtr-security` and lists `SecurityBundle`.
- Read [Build a web application](web-application.md), because a firewall runs
  over the request lifecycle.
- Confirm that the bundle is active:

  ```sh
  uv run shop debug:bundles
  ```

  The table shows `security` as `listed` and `active`.

## Procedure

### Hash a password

A user provider keeps the hash of a password, never the password.

1. Name the hasher of each user class in
   `src/shop/config/packages/security.py`:

   ```python
   from xtr_dependency_injection import configure
   from xtr_security_core import InMemoryUser
   from xtr_security.bundle import AutoHasherConfig, SecurityConfig


   @configure
   def security() -> SecurityConfig:
       return SecurityConfig(password_hashers={InMemoryUser: AutoHasherConfig()})
   ```

   `AutoHasherConfig` hashes with argon2id.
2. Hash the password:

   ```sh
   uv run shop security:hash-password
   ```

   The command asks for the password and shows the hash under
   `Password hash:`.
3. Copy the hash. The next task stores it.

> [!WARNING]
> Do not pass the password as an argument of the command. The shell history and
> the list of processes keep it. The command prompts for it, and it reads `-`
> from standard input.

### Declare the users

1. Add a provider to `SecurityConfig`. This provider declares its users in the
   configuration file:

   ```python
   from xtr_security_core import InMemoryUser
   from xtr_security.bundle import AutoHasherConfig, InMemoryUserProviderConfig, SecurityConfig

   USERS = {
       "ada": {"password": "$argon2id$v=19$m=65536,...", "roles": ["ROLE_ADMIN"]},
   }


   @configure
   def security() -> SecurityConfig:
       return SecurityConfig(
           password_hashers={InMemoryUser: AutoHasherConfig()},
           providers={"staff": InMemoryUserProviderConfig(users=USERS)},
       )
   ```

   Replace the value of `password` with the hash of the last task.
2. For users in a database, use `ServiceUserProviderConfig(service=MyProvider)`
   instead, and register `MyProvider` as a service.

### Add a firewall

1. Add a firewall that claims the paths below `/books`. Add `FIREWALL` to the
   same file, and change the `security` function:

   ```python
   from xtr_security.bundle import FirewallConfig, HttpBasicConfig

   FIREWALL = FirewallConfig(
       pattern=r"^/books",
       provider="staff",
       authenticators=(HttpBasicConfig(realm="shop"),),
   )


   @configure
   def security() -> SecurityConfig:
       return SecurityConfig(
           password_hashers={InMemoryUser: AutoHasherConfig()},
           providers={"staff": InMemoryUserProviderConfig(users=USERS)},
           firewalls={"main": FIREWALL},
       )
   ```

   `pattern` is a regular expression matched against the path of the request.
   `provider` names the provider of the last task. `HttpBasicConfig` reads the
   `Authorization: Basic` header of the request.
2. Describe the firewall:

   ```sh
   uv run shop debug:firewall main
   ```

   The command shows `Secured: yes` and
   `Entry point: HttpBasicAuthenticator`.

> [!NOTE]
> The bundle matches the firewalls in order, and the first match wins. A
> request that no firewall claims reaches the route with no caller.

### Add an access rule

A firewall says who the caller is. An access rule says what the caller must
hold.

1. Add the rule to the `security` function:

   ```python
   from xtr_security.bundle import AccessControlConfig


   @configure
   def security() -> SecurityConfig:
       return SecurityConfig(
           password_hashers={InMemoryUser: AutoHasherConfig()},
           providers={"staff": InMemoryUserProviderConfig(users=USERS)},
           firewalls={"main": FIREWALL},
           access_control=(AccessControlConfig(path=r"^/books", attribute="ROLE_ADMIN"),),
       )
   ```

   `attribute` is one role, `"IS_AUTHENTICATED"`, `"PUBLIC_ACCESS"` or an
   `"OAUTH2_SCOPE(...)"` string.
2. Put a narrow rule before a broad rule, because the bundle tries the rules in
   order.
3. Start the server:

   ```sh
   uv run shop-web
   ```

4. Ask for the protected path with no credentials:

   ```sh
   curl -si localhost:8000/books
   ```

   The answer is `401 Unauthorized` with
   `www-authenticate: Basic realm="shop"`.
5. Ask again with the credentials:

   ```sh
   curl -si -u ada localhost:8000/books
   ```

   `curl` asks for the password, and the answer is `200 OK`.
6. Push `Ctrl-C` to stop the server.

### Read the caller in a route

1. Ask for the caller with the `CurrentUser` dependency:

   ```python
   from typing import Annotated

   from xtr_security_core.user.user_interface import UserInterface
   from xtr_security_http import CurrentUser


   @router.get("/books/me", name="books_me")
   async def books_me(user: Annotated[UserInterface, CurrentUser()]) -> dict[str, str]:
       """Answer with the identifier of the caller."""
       return {"user": user.get_user_identifier()}
   ```

2. To protect one route instead of a path, add the `IsGranted` decorator below
   the decorator of the route:

   ```python
   from xtr_security_http import IsGranted


   @router.delete("/books/{isbn}", name="books_delete")
   @IsGranted("ROLE_ADMIN")
   async def books_delete(isbn: str) -> None: ...
   ```

### Keep the secrets out of the repository

Three configurations sign with a secret: the remember-me cookie, the login link
and the counting of the logins. The bundle never makes one.

1. Read each secret from the environment:

   ```python
   from xtr_dependency_injection import env
   from xtr_security.bundle import RememberMeConfig

   RememberMeConfig(secret=env("REMEMBER_ME_SECRET"))
   ```

2. Put the value in `.env.local`, which `.gitignore` excludes.

> [!WARNING]
> Never write a secret in `.env` or in a configuration file. Git tracks both
> files. The service that needs the secret fails at the first use, and it names
> the setting.

## Next step

- [Test an application](testing.md) drives a protected route in a test.
- [Configure a bundle](configuration.md) changes a configuration value for one
  environment.
- The
  [xtr-security README](https://github.com/xterr/python-xtr/tree/main/packages/xtr-security)
  describes every field of `SecurityConfig` and the nine authenticators. It
  also describes the token handlers, the stateful firewalls, the logout, the
  login throttling and the switch of a user.
- The
  [xtr-security-http README](https://github.com/xterr/python-xtr/tree/main/packages/xtr-security-http)
  describes the HTTP edge: the authenticators, the passports and the badges.
- The
  [xtr-security-core README](https://github.com/xterr/python-xtr/tree/main/packages/xtr-security-core)
  describes the users, the tokens, the voters and the decision manager.
- The [API reference](https://xterr.github.io/python-xtr/api/xtr_security/)
  lists every class of the bundle.
