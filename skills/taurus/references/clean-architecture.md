> Load when: Layering, dependency direction, ports and adapters, and where each kind of code belongs. Load when creating a new module, service, or package, when deciding where a piece of logic goes, when a file starts importing framework or driver types, or when reviewing structure. Includes reference layouts for Go, TypeScript/Node, Next.js, and Python.

# Clean architecture

## The one invariant

Dependencies point inward only.

```
infrastructure  ->  adapters  ->  application  ->  domain
```

domain imports nothing but the standard library and its own types. No ORM, no
HTTP framework, no SQL driver, no Redis, no Kafka, no cloud SDK, no PSP client, no
workflow engine, no logger from a framework. When a domain file needs one of those,
the design is wrong, and the fix is a port.

Everything else in this skill is a layout convention. The dependency rule is the
part that is not negotiable.

## Layers

**domain.** Entities, value objects, aggregates, domain events, domain errors,
invariants, and the repository and service *interfaces* (ports). Pure logic,
deterministic, testable with no I/O and no mocks. Business rules live here, and
nowhere else.

**application.** Use cases. One type or function per use case, orchestrating domain
objects and ports. Owns the transaction boundary. Owns the sequence. Contains no
SQL, no HTTP, no serialization. Knows nothing about who called it.

**adapters.** Two directions.
- Inbound: HTTP handlers, gRPC servers, CLI commands, message consumers, cron
  entrypoints. They decode, validate transport shape, build a command, call one use
  case, map the result or error to a response. Nothing else.
- Outbound: repository implementations, PSP clients, queue producers, cache clients,
  mail senders. Each implements a port defined in domain.

**infrastructure.** Wiring, config, connection pools, migrations, observability
setup, dependency injection, server bootstrap.

## Rules that fail review

- A domain type importing a driver, framework, or SDK type.
- An inbound handler calling two or more outbound adapters directly.
- Business rules in a handler, a repository, or a migration.
- A use case that constructs its own database connection or HTTP client.
- A repository that returns an ORM entity to the application layer.
- Anemic domain: entities with only getters and setters while the rules live in a
  *Service class.
- A shared utils, common, helpers, or models package that everything imports.
  Name modules after the domain concept.
- Circular imports between layers, in either direction.
- A transaction opened in a handler, or held open across a network call to another
  service.

## Ports

Define the port where it is used, in the language of the domain.

```go
// internal/inventory/domain/ports.go
type SeatHoldRepository interface {
    HoldSeats(ctx context.Context, occurrenceID OccurrenceID, seats []SeatID, holder HolderID, until time.Time) (*Hold, error)
    ReleaseExpired(ctx context.Context, now time.Time) (int, error)
}
```

The interface names domain concepts. It does not mention SQL, rows, or transactions.
The Postgres implementation lives in adapters/postgres. Keep interfaces narrow:
one caller, one method set. A twelve-method repository interface is a sign the
boundary is in the wrong place.

## Reference layouts

Adjust to the project's existing convention. Consistency with the repo beats
consistency with this file.

**Go**

```
cmd/<binary>/main.go
internal/<bounded_context>/
    domain/          entities, value objects, ports, domain errors
    application/     use cases, transaction boundaries
    adapters/
        http/        handlers, request and response DTOs
        postgres/    repository implementations
        kafka/       producers, consumers
    infrastructure/  config, pools, wiring, telemetry
api/                 OpenAPI, protobuf
migrations/
test/                integration, contract, load
```

**TypeScript / Node**

```
src/
  modules/<context>/
    domain/          entities, value objects, ports (interfaces), errors
    application/     use cases
    adapters/
      http/          controllers, DTOs, validators
      persistence/   repository implementations
  shared/kernel/     value objects shared across contexts, nothing else
  infrastructure/    config, DI container, clients
```

**Next.js.** Route handlers and server actions are inbound adapters. They call a use
case from src/modules/<context>/application and map the result. Business logic
never lives in app/, in a React component, or in a server action body. Server
components fetch through the same use cases.

**Python**

```
src/<package>/
  <context>/
    domain/          dataclasses, protocols, errors
    application/     use cases
    adapters/        fastapi routers, sqlalchemy repositories
  infrastructure/    settings, session factory, wiring
```

## Testing by layer

| Layer | Test | Doubles |
|---|---|---|
| domain | unit, exhaustive on the rules | none |
| application | unit against in-memory port fakes | fakes you own, never mocks of third-party types |
| adapters inbound | contract test on the transport shape | fake use case |
| adapters outbound | integration against the real dependency in a container | none |
| end to end | a few paths that cover the wiring | none |

## Where does this code go?

1. Is it a business rule that stays true regardless of delivery mechanism? domain.
2. Is it a sequence of steps that fulfills one user intent? application.
3. Does it translate between the outside world and the core? adapter.
4. Is it wiring, config, or a connection? infrastructure.
5. Does it not fit any of those? The concept is missing a name. Find the domain
   concept before writing the code.
