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

## Design decisions

- **`@/lib/api/client` is mocked globally** in CVCard tests: the client uses MSAL which
  requires a browser MSAL instance. Rather than setting up a full MSAL context, the
  entire client module is mocked with `jest.fn()` stubs.
- **`@/lib/theme/index` is mocked** in useTheme tests to prevent actual CSS variable
  mutations in jsdom (which has no rendered CSS engine).
- **`URL.createObjectURL` / `revokeObjectURL`** are mocked in `jest.setup.ts` because
  jsdom does not implement the File/Blob URL API.

## Intentionally excluded

- `lib/api/client.ts` API function tests: the client uses MSAL token acquisition
  (`acquireTokenSilent`/`acquireTokenRedirect`) which requires a real browser MSALContext.
  The axios instance itself is tested indirectly through component mocks. A dedicated
  integration test with MSAL configured would be the right vehicle for these.
