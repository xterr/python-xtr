# Credits

Most xtr packages are translations into Python of PHP libraries: their design, their names and
much of their behaviour come from the projects below. Thank you to their authors and
contributors.

| Project | Translated into |
|---|---|
| [Symfony](https://symfony.com) | xtr-cache, xtr-cache-contracts, xtr-clock, xtr-console, xtr-dependency-injection, xtr-dotenv, xtr-event-dispatcher, xtr-event-dispatcher-contracts, xtr-http-client, xtr-http-client-contracts, xtr-http-foundation, xtr-http-kernel, xtr-lock, xtr-logging, xtr-messenger, xtr-orm, xtr-password-hasher, xtr-rate-limiter, xtr-recipes, xtr-remote-event, xtr-scheduler, xtr-security, xtr-security-core, xtr-security-csrf, xtr-security-http, xtr-service-contracts, xtr-webhook |
| [Monolog](https://github.com/Seldaek/monolog) | xtr-logging |
| [PSR-3 Logger Interface](https://github.com/php-fig/log) (PHP-FIG) | xtr-logging-contracts |
| [PSR-7 HTTP Message Interfaces](https://github.com/php-fig/http-message) and [PSR-17 HTTP Factories](https://github.com/php-fig/http-factory) (PHP-FIG) | xtr-http-message-contracts |
| [nyholm/psr7](https://github.com/Nyholm/psr7) (Tobias Nyholm) and [php-http/psr7-integration-tests](https://github.com/php-http/psr7-integration-tests) (PHP HTTP Team) | xtr-http-message |
| [Flysystem](https://flysystem.thephpleague.com) and [FlysystemBundle](https://github.com/thephpleague/flysystem-bundle) | xtr-storage |
| [Doctrine Migrations](https://github.com/doctrine/migrations), [DoctrineBundle](https://github.com/doctrine/DoctrineBundle) and [DoctrineMigrationsBundle](https://github.com/doctrine/DoctrineMigrationsBundle) | xtr-orm |
| [LexikJWTAuthenticationBundle](https://github.com/lexik/LexikJWTAuthenticationBundle) | xtr-security-jwt |
| [thephpleague/oauth2-server](https://github.com/thephpleague/oauth2-server) (Alex Bilbie) and its token revocation and introspection [pull request #1473](https://github.com/thephpleague/oauth2-server/pull/1473) (Hafez Divandari) | xtr-security-oauth2-server, xtr-security-oauth2-server-core |
| [thephpleague/oauth2-server-bundle](https://github.com/thephpleague/oauth2-server-bundle) (Robin Chalas, Trikoder) | xtr-security-oauth2-server |

All of them are released under the MIT license. Each package's `LICENSE` carries the copyright
lines of the projects it was translated from.
