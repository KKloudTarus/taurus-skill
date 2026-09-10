> Load when: Implementing or reviewing browser-facing behavior, components, forms, routing, responsive layouts, accessibility, hydration, frontend API integration, or user-perceived performance. Defines feature-level quality checks without imposing a backend architecture on the UI.

# Frontend quality

Review the experience as a state machine, not a screenshot. For each user intent, cover
initial, loading, success, empty, validation, partial, unauthorized, offline, timeout,
retry, and stale-response states that can actually occur.

## Accessibility

Use WCAG 2.2 Level AA as the default target unless the product names another standard.
Automated tools catch only part of the problem, so combine them with keyboard and screen
reader checks on critical journeys.

- Prefer semantic HTML before ARIA. Every control has an accessible name, and labels,
  descriptions, errors, and required state are programmatically associated.
- All behavior works by keyboard. Focus is visible, follows a logical order, and moves
  intentionally after dialogs, route changes, validation failures, and dynamic updates.
- Do not use color, position, hover, or motion as the only carrier of information. Respect
  reduced-motion and zoom, and keep content usable during text reflow.
- Images, icons, audio, and video have alternatives appropriate to their purpose.
- Loading and error updates are announced without repeatedly interrupting the user.

## State and async behavior

Keep state at the narrowest owner and derive values instead of synchronizing duplicates.
Separate local interaction state, URL state, server cache, and durable browser state.
Define which source wins when they disagree.

Cancel or ignore stale requests. Test response reordering, double submission, navigation
during mutation, retry after partial success, expired sessions, and optimistic rollback.
Disablement is not an idempotency guarantee; the server still owns durable invariants.

Render meaningful HTML before optional client enhancement when the framework supports it.
Server and client output must agree at hydration time. Browser-only APIs, locale, time,
random values, and responsive branches often create mismatches.

## Contracts, security, and compatibility

Treat the frontend/backend boundary as a versioned contract. Generate or validate types
from the authoritative OpenAPI, GraphQL, or schema source where practical. Test missing
optional fields, new enum values, old clients, structured errors, pagination, and auth
expiry. A TypeScript type does not validate network data at runtime.

Keep tokens and sensitive data out of URLs, analytics, logs, local storage, and rendered
HTML. Treat API content, Markdown, translations, and model output as untrusted at every
HTML or URL sink. Prefer secure cookies for browser sessions when the threat model allows.

Define the supported browser and device matrix from product evidence. Test critical paths
on actual engines represented in that matrix, including touch and narrow viewports. Avoid
browser detection when capability detection expresses the requirement.

## Performance and resilience

Measure Core Web Vitals with field data when available and lab data for regression. Find
the actual LCP element, INP interaction, and layout-shift source. Protect a route-level
budget for JavaScript, images, fonts, third-party scripts, request waterfalls, and cache
behavior; a high aggregate score does not explain which user path regressed.

Load code and data at the feature boundary, but avoid waterfalls hidden behind nested
components. Reserve media dimensions, prioritize the real above-the-fold resource, and
move nonessential third parties off the critical path. Test slow network, CPU pressure,
cache miss, service-worker update, and backend failure where the product supports them.

## Test selection

- Pure tests for calculations, reducers, parsers, and state transitions.
- Component tests for semantics, focus, forms, async states, and user interactions.
- Contract tests for transport mapping and backward-compatible API evolution.
- Browser tests for a small set of critical journeys across the supported matrix.
- Automated accessibility scans plus manual keyboard and assistive-technology checks.
- Field telemetry or reproducible lab traces for performance claims.

Assert what a user can perceive or do. Snapshot volume, CSS selectors tied to layout, and
mock call order make refactors expensive without proving the journey works.

## Review evidence

```text
JOURNEYS: <critical paths and states exercised>
ACCESSIBILITY: <standard, automation, keyboard/manual evidence>
BROWSERS: <supported matrix and observed results>
CONTRACT: <schema source and compatibility cases>
PERFORMANCE: <field or lab evidence and affected route>
FINDINGS: <severity, reproduction, user impact, fix>
```

## Primary sources

- WCAG 2.2: https://www.w3.org/TR/wcag/
- WAI techniques and test material: https://www.w3.org/WAI/standards-guidelines/wcag/docs/
- OpenAPI Specification: https://spec.openapis.org/oas/latest.html
- Core Web Vitals: https://web.dev/articles/vitals
- React state structure: https://react.dev/learn/choosing-the-state-structure
- React Effects: https://react.dev/learn/you-might-not-need-an-effect
- Angular style guide: https://angular.dev/style-guide
- Next.js project organization: https://nextjs.org/docs/app/getting-started/project-structure
