> Load when: Choosing module boundaries, dependency direction, ports and adapters, or placement of business logic in backend or frontend code. Use when a change adds a service, package, feature, framework integration, persistence mechanism, or architectural seam. Includes idiomatic Go guidance, general Hexagonal Architecture, and feature-oriented frontend guidance.

# Architecture boundaries

Architecture protects policy from details that change for different reasons. It is
not a required folder tree. Start with the repository and language conventions, then
introduce a boundary only when it reduces a real coupling or makes an important rule
testable without external machinery.

## The shared principle

Clean Architecture and Hexagonal Architecture use different diagrams but agree on the
important dependency rule: application policy does not depend on a UI, database,
framework, message broker, or vendor SDK. Adapters translate between those mechanisms
and ports owned by the application side of the boundary.

```
driving adapter -> application/core <- driven adapter
                       owns ports
```

Runtime control can travel outward through a port while source dependencies still
point toward the core. Data crossing the boundary uses application-shaped values,
not ORM records, HTTP request objects, framework contexts, or generated SDK models.

Do not equate this with four mandatory layers. Cockburn's original Hexagonal pattern
describes an application inside ports with adapters around it. Clean Architecture adds
circles for enterprise rules, use cases, interface adapters, and frameworks, while
explicitly allowing a different number of circles. Small CRUD services and simple UI
features often need fewer boundaries.

## Decide whether a boundary earns its cost

Create a port when the application has a real consumer-side need to replace, isolate,
or test an external capability. Good candidates include persistence, clocks, payment
providers, queues, file storage, and nondeterministic services. Keep direct calls when
the wrapper would only rename a stable library API and no policy needs isolation.

A boundary is useful when at least one condition holds:

- Business rules must run without the database, network, browser, or framework.
- Two adapters drive the same capability, such as HTTP and a queue consumer.
- An external dependency has a credible replacement, failure mode, or test seam.
- A feature has a different change cadence or owner from the mechanism around it.

Avoid speculative interfaces, one-method pass-through layers, global `utils` buckets,
and DTO mapping that copies fields without protecting a boundary.

## Responsibilities

**Domain policy** holds invariants and calculations that remain meaningful without a
delivery mechanism. Rich domain objects are useful for complex business rules; they
are unnecessary ceremony for a read-only projection or straightforward CRUD.

**Application behavior** coordinates one user or system intent, decides the atomic
unit, and calls ports. It may use domain objects, or it may be the core itself when the
domain is simple. It does not construct concrete database or HTTP clients.

**Driving adapters** translate HTTP, CLI, UI events, schedules, or messages into an
application call. **Driven adapters** implement capabilities such as persistence,
email, queues, browser storage, and external APIs. The composition root selects and
wires concrete adapters.

## Go: use ports and adapters idiomatically

Go has no official “Clean Architecture layout.” The official module guide recommends
starting with the smallest useful package structure, using `internal` to protect
implementation packages, and using `cmd` when a repository contains multiple commands.
Package names should be short, meaningful, and provide context to callers; `util`,
`common`, `types`, `interfaces`, and generic layer names tend to hide weak boundaries.

Go interfaces belong in the package that consumes the behavior. Do not put every
repository interface in a central `domain/ports.go`, and do not define an interface
beside its only implementation for mocking. Start with concrete types. When a consumer
needs a seam, define the smallest interface there; the implementing package normally
returns a concrete type.

```go
// internal/ordering/service.go: the consumer owns the port.
package ordering

type OrderStore interface {
    Save(ctx context.Context, order Order) error
    ByID(ctx context.Context, id OrderID) (Order, error)
}

type Service struct {
    orders OrderStore
    clock  Clock
}
```

```go
// internal/postgres/orders.go: concrete adapter, wired in cmd/api.
package postgres

type Orders struct {
    db *sql.DB
}

func NewOrders(db *sql.DB) *Orders { return &Orders{db: db} }
```

The adapter may import `ordering` values to satisfy the consumer-owned contract.
`ordering` must not import `postgres`. Go rejects import cycles, but an acyclic graph
can still point the wrong way, so inspect imports from the core packages directly.

An idiomatic service can begin this small:

```
cmd/api/main.go                 composition root
internal/ordering/             cohesive policy and use cases
internal/httpapi/              driving HTTP adapter
internal/postgres/             driven persistence adapter
internal/platform/             narrowly shared operational code
migrations/                    database migrations
```

Split `internal/ordering` further only when it has distinct cohesive packages with
clear client-facing names. Avoid recreating `domain/application/adapters/infrastructure`
under every feature by default. Keep tests beside the package they exercise; use
external `_test` packages when testing through the public surface is valuable.

Pass `context.Context` as the first parameter along request-scoped call chains, but do
not store it in domain state. Context carries cancellation and deadlines; business
rules should receive explicit domain values instead of reading arbitrary context keys.

## Backend languages with explicit modules

Java, Kotlin, C#, TypeScript, and Python can express Hexagonal Architecture with
packages, projects, or import rules. Organize by business capability first. Add
internal layers inside a capability when its complexity warrants them.

```
orders/
  domain/                 business rules, when a rich model exists
  application/
    ports/                contracts needed by application behavior
    use-cases/
  adapters/
    inbound/              HTTP, CLI, message consumers
    outbound/             database, queue, vendor clients
  bootstrap/              composition and framework startup
```

For a small capability, collapse `domain` into `application` and keep ports next to
their consumers. For a large .NET solution, separate projects can make dependency
direction compiler-visible: UI and Infrastructure reference Application Core, while
the core references neither. In TypeScript or Python, use linted import boundaries or
package separation when folders alone cannot enforce the graph.

The port is named in application language. A persistence port might expose
`reserveSeats` rather than `executeQuery`; an outbound adapter owns SQL, ORM entities,
serialization, retries specific to its client, and mapping at the boundary.

## Frontend: feature boundaries before backend layers

Frontend architecture should preserve framework strengths instead of forcing every
component through a backend-shaped use-case class. Organize by user-facing feature and
colocate the view, local state, tests, and feature-specific adapters. Angular's official
style guide recommends feature areas rather than top-level `components`, `services`,
and `directives` buckets. Next.js explicitly allows colocation and feature or route
organization inside or outside `app`.

```
src/
  app/ or routes/          routing, layouts, composition
  features/checkout/
    ui/                    components and presentation
    model/                 feature state and pure business calculations
    api/                   HTTP adapter and transport mapping
    checkout.ts            public feature surface
  shared/                  proven cross-feature code only
```

Use a Hexagonal boundary inside a frontend feature when it contains substantial policy
or must switch between browser APIs, remote APIs, local storage, workers, or multiple
views. In that case, UI events drive feature behavior and API/storage modules act as
driven adapters. A simple form that validates and submits one endpoint does not need a
domain entity, repository interface, and use-case class.

Keep state near the feature that owns it. React's official guidance favors one source
of truth, avoids redundant or contradictory state, derives values during render, and
uses Effects only to synchronize with external systems. Network/server state, local UI
state, URL state, and durable client state have different lifecycles; do not duplicate
one into another without an explicit synchronization rule.

Framework entrypoints stay thin in the architectural sense: they may compose views,
load data, and handle framework lifecycle, but durable business invariants belong in
pure feature code that can run without rendering. Server actions and route handlers
are transport boundaries, not automatic homes for business rules.

## Review checks

- Can the important policy run in a test without its external mechanisms?
- Does each interface belong to a real consumer and expose only what it needs?
- Do adapters translate external types at the boundary instead of leaking them inward?
- Does the composition root own concrete construction?
- Is the package or feature name meaningful from a caller's point of view?
- Would removing a layer make the code clearer without coupling policy to a mechanism?
- In frontend code, is each piece of state owned once and placed at the narrowest
  scope that needs it?
- Does the proposed layout follow the framework's routing, colocation, and lifecycle
  conventions?

## Primary sources

- Alistair Cockburn, original Hexagonal Architecture: https://alistair.cockburn.us/hexagonal-architecture/
- Robert C. Martin, The Clean Architecture and Dependency Rule: https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
- Go module organization: https://go.dev/doc/modules/layout
- Go package names: https://go.dev/blog/package-names
- Go interfaces and context review guidance: https://go.dev/wiki/CodeReviewComments
- Angular feature-oriented structure: https://angular.dev/style-guide
- Next.js project organization and colocation: https://nextjs.org/docs/app/getting-started/project-structure
- React state ownership: https://react.dev/learn/choosing-the-state-structure
- React Effects as external synchronization: https://react.dev/learn/you-might-not-need-an-effect
- Microsoft application-core dependency guidance: https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/common-web-application-architectures
