# Frontend Unit Tests

## How to run

From the `JobFinder/frontend/` directory:

```bash
# Install dependencies (once)
npm install

# Run all tests
npm test

# Run in watch mode
npm run test:watch
```

## Modules covered

| Test file | Module under test | What is tested |
|---|---|---|
| `utils.test.ts` | `lib/utils.ts` | `cn()` — class merging, falsy filtering, tailwind-merge dedup |
| `useTheme.test.tsx` | `lib/theme/useTheme.ts` | Initial state, localStorage persistence, toggle behaviour |
| `CVCard.test.tsx` | `app/_components/CVCard.tsx` | Status rendering (pending/processing/error/done), delete state machine, onSelect callback |
| `MatchItem.test.tsx` | `app/_components/MatchItem.tsx` | Score colour bands, expired badge, link vs text, expand/collapse, ROME label |
| `MatchList.test.tsx` | `app/_components/MatchList.tsx` | Loading skeleton, empty state, list rendering |
| `client.test.ts` | `lib/api/client.ts` | Request interceptor single-flight `acquireTokenRedirect`: concurrent callers share one in-flight redirect; a prior failed redirect doesn't block a later retry |
| `LibrarySection.test.tsx` | `app/_components/LibrarySection.tsx` | "Ajouter un CV" calls the `onAddCv` prop (no direct upload call — upload/validation live in `UploadSection.handleFile`); `onCvsChange` fires on local deletion, not just fetches; add-CV slot hidden once the CV quota is reached |
| `NotificationDaysToggle.test.tsx` | `app/profile/_components/NotificationDaysToggle.tsx` | Renders all seven days, pressed state reflects `value`, clicking toggles a day in/out of the selection (including clearing the last selected day) |
| `UnsavedChangesContext.test.tsx` | `lib/navigation/UnsavedChangesContext.tsx` | `confirmNavigation` resolves immediately when clean; when dirty, the dialog's Annuler/Quitter sans enregistrer/Enregistrer et quitter each resolve the right outcome, the last one invoking the registered save handler and surfacing its failure |
| `ProfilePage.test.tsx` | `app/profile/page.tsx` | `notification_days` auto-save: debounced into a single `PUT` containing only `notification_days`, collapses several toggles within the window, doesn't mark the page dirty; `handleSave` never sends `notification_days` |

## Design decisions

- **`@/lib/api/client` is mocked globally** in CVCard tests: the client uses MSAL which
  requires a browser MSAL instance. Rather than setting up a full MSAL context, the
  entire client module is mocked with `jest.fn()` stubs.
- **`@/lib/theme/index` is mocked** in useTheme tests to prevent actual CSS variable
  mutations in jsdom (which has no rendered CSS engine).
- **`URL.createObjectURL` / `revokeObjectURL`** are mocked in `jest.setup.ts` because
  jsdom does not implement the File/Blob URL API.
- **`ProfilePage.test.tsx` mocks `@/lib/navigation/UnsavedChangesContext`** (in addition
  to `@azure/msal-react`, `next/navigation`, `posthog-js`, and `@/lib/auth/msalConfig`,
  which fail-fasts on missing `NEXT_PUBLIC_ENTRA_*` env vars at import time) — the guard
  itself is covered in isolation by `UnsavedChangesContext.test.tsx`, so the page test
  only needs a stub confirming it's *called* the right way, not a full dialog flow.
- **`client.test.ts` mocks `@/lib/auth/msalInstance` and `@/lib/auth/msalConfig`
  directly** (instead of mocking `@/lib/api/client` itself, since it's the module under
  test) — this avoids needing a real browser MSALContext or the `NEXT_PUBLIC_ENTRA_*`
  env vars the real `msalConfig.ts` requires. Each test calls `jest.resetModules()` to
  get a fresh copy of the module-level `redirectInFlight` single-flight flag, and
  requires `InteractionRequiredAuthError` via `jest.requireActual` after that reset
  (not via a top-level `import`) so the thrown instance and `client.ts`'s `instanceof`
  check share the same module registration.

## Intentionally excluded

- `lib/api/client.ts` end-to-end token acquisition (`acquireTokenSilent` success path,
  real token injection into `Authorization`): still requires a real browser MSALContext.
  `client.test.ts` covers the interceptor's single-flight redirect logic with a mocked
  MSAL instance; a dedicated integration test with MSAL configured would be the right
  vehicle for the rest.
