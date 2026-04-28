# EnrichSalesAgent

**Tradeshow intelligence for industrial CEOs.**

EnrichSalesAgent turns a company name into a decision-ready briefing card in under 60 seconds. Type a name, hit **Enrich**, and walk up to the booth knowing who they are, what they make, where they sell, and who to ask for.

---

## What it does

- **Single-input search.** Company name + optional context (tradeshow, hall, focus area).
- **Live research flow.** The client shows progressive research steps while the backend builds the final briefing card.
- **Briefing card.** A structured, source-cited intelligence card optimized for a 30-second read before a booth visit:
  - Company identity bar (HQ, founded, employees, revenue with confidence)
  - Geography badge (target market vs. flagged region)
  - Product line and company snapshot
  - Aftermarket footprint and recent signals
  - "Right person at the booth" — verified name + title, or a role estimate (never a fabricated name)
  - Opening line you can copy and use
  - Numbered source footer
- **Export.** One-click copy of the full briefing to clipboard, formatted for sharing.
- **Mock mode.** Fully demoable with no backend.

---

## Tech stack

- **React 18** + **TypeScript 5**
- **Vite 5** build tooling
- **Tailwind CSS v3** with a hand-built design system (HSL tokens in `src/index.css`)
- **lucide-react** icons
- **Vitest** for tests
- Lightweight research client (`src/hooks/useEnrichStream.ts`) — no external data client required


---

## Getting started

### Prerequisites

- Node.js 18+ (or Bun)
- npm, pnpm, or bun

### Install

```bash
npm install
```

### Run in mock mode (default)

```bash
npm run dev
```

Open http://localhost:8080. Type any company name and click **Enrich** — a simulated 13-step research flow will run and produce a full briefing card.

### Run against a live backend

Create a `.env` file (copy `.env.example`):

```
VITE_MOCK_MODE=false
VITE_API_BASE_URL=http://127.0.0.1:8000
```

The backend is expected to expose a JSON endpoint at:

```
POST {VITE_API_BASE_URL}/research
```

---

## Scripts

| Command            | Purpose                              |
| ------------------ | ------------------------------------ |
| `npm run dev`      | Start the Vite dev server            |
| `npm run build`    | Production build to `dist/`          |
| `npm run preview`  | Preview the production build locally |
| `npm run lint`     | ESLint over the project              |
| `npm run test`     | Run the Vitest suite once            |
| `npm run test:watch` | Vitest in watch mode               |

---

## Project structure

```
src/
  components/
    BriefingCard/         Hand-crafted briefing surface (identity, products, geography, signals, booth contact, sources)
    BriefingPreview.tsx   Progressive reveal during streaming
    InputForm.tsx         Search input + extra context
    ProgressFeed.tsx      Live agent log
    ProgressView.tsx      Progress + preview layout
    StickyActionBar.tsx   Footer actions (new search, export)
    ErrorView.tsx         Network / timeout recovery
    Header.tsx            header (BETA badge)
  hooks/
    useEnrichStream.ts    Research request client + mock mode driver
  pages/
    Index.tsx             State machine: input → progress → briefing
  types/
    briefing.ts           Strict data model
  utils/
    clipboard.ts          Briefing export formatter
    geography.ts          Target / flagged market classification
  index.css               Design tokens + animations
```

---

## Design system

All colors are defined as HSL CSS variables in `src/index.css` and mapped in `tailwind.config.ts`. Components use semantic tokens only (`bg-background`, `text-primary-ink`, `border-border`, etc.) — never hardcoded colors.

Brand:

- Primary orange `#F97316` (`--primary`)
- Primary text `#111827` (`--text-primary`)
- White surfaces, subtle borders, restrained shadows
- Inter for UI, IBM Plex Mono for source chips and metadata

Animations: `shimmer` (skeletons), `section-in` / `fade-up` (reveals), `pulse-flag` (geography warnings).

---

## Verification rules (important)

The briefing card enforces a few rules that must not be relaxed:

1. **Booth contact name** is only rendered when `isVerified === true` **and** a `sourceUrl` is present. Otherwise the card shows a role estimate, not a name.
2. **Revenue** without `revenueConfidence === 'confirmed'` is shown in the warning color.
3. Every claim with a citation links to a numbered entry in the **Sources** footer.

These rules live in the corresponding components under `src/components/BriefingCard/` — keep them intact.

---

## License

Proprietary — © All rights reserved.
