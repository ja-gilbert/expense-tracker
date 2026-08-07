# Frontend design direction

Reference material for the dashboard redesign. **Nothing here is wired to the
app** — it's a target to build against, not code to import.

- **`dashboard-mockup.html`** — the chosen direction, "Refined dark". Open it
  directly in a browser: no CDN, no build step, no network. Hover the charts;
  the crosshair and tooltips are real.

The mockup is a single self-contained file. Its `:root` block is the design
token set, its inline `<script>` holds ~130 lines of dependency-free SVG chart
code, and the demo data uses the real `CATEGORIES` list and `Expense` schema
from `app.py`.

---

## 1. What's wrong with the current frontend

`templates/index.html` isn't ugly — it's *undifferentiated*. Every element has
the same visual weight, so nothing reads as important.

| Problem | Where | Why it matters |
|---|---|---|
| **No hierarchy.** Filters, Add form, table, and charts are all `rounded-2xl border-slate-800 bg-slate-900 p-4`. | everywhere | Every card shouts equally, so the eye has no entry point. A dashboard needs exactly one hero number. |
| **The total is rendered twice**, 60px apart, identically styled. | `index.html:69-76` and `144-151` | Duplicated data reads as a bug, and neither instance is emphasised. |
| **Cards and page are both `slate-900`.** | `base.html:19`, `index.html:19` | Only a border separates a card from the background, so nothing lifts. Cards need a *lighter* surface than the page. |
| **Charts are unstyled Chart.js defaults.** | `index.html:238-265` | Default pie colors aren't colorblind-safe, the bar legend uses `#334155` (invisible on `slate-900`), and gridlines are heavier than the data. |
| **A pie chart for 5 nominal categories.** | `catChart` | Pie only works for part-to-whole at a glance with ≤6 slices, and it's bad at comparing close values. Rent is ~56% of the data, so the other four are unreadable slivers. |
| **Rent flattens every trend chart.** | `dayChart` | One $1,450 bar makes the other 29 days visually zero. This is a *data* problem, not a styling one — and it's the single biggest readability win available. |
| **Filters and the Add form compete** for the same row. | `index.html:16-141` | Unrelated tasks: filters scope the whole page, adding is a write. Side by side implies they're peers. |
| **Edit is a full page navigation.** | `edit.html` | You lose filters, scroll position, and your place in the table for a one-field change. |
| **Reset link is `href="#"`.** | `index.html:62` | Dead control. Already in `PLAN.md` backlog. |
| **`bg-brand/20 text-brand` buttons.** | `index.html:55, 134` | A 20%-opacity fill with brand-colored text is low contrast and reads as *disabled*, not primary. |
| **No empty / loading / error states** beyond one table row. | | |

Two things that already work and should survive the redesign: the
flash-message block in `base.html` is clean, and `parse_expense_form` /
`apply_expense_filters` mean the backend can feed more UI without duplicating
logic.

---

## 2. Design decisions the mockup encodes

These are the substance. The dark palette is the easy part.

**One hero number.** "Spent in the last 30 days" at 48px+. Everything else is
secondary. Never two.

**One filter row, above everything it scopes.** Date presets (7d / 30d / 90d /
MTD / Custom) plus category chips. No per-card filters. Every chart, the table,
*and the CSV export* re-render against the same slice — which is exactly the
inconsistency `PLAN.md` flags in `export_csv()`.

**Separate fixed from variable spending.** Rent dominates the period, so the
trend chart defaults to *variable* spend with recurring charges excluded, with a
toggle to include them. This is what makes the chart worth looking at.

**Kill the pie.** Category breakdown becomes a ranked horizontal bar chart — one
series, one color, length carries the value. Never color bars by rank; that
double-encodes magnitude and burns the only free channel.

**Budgets as meters, not another chart.** Per-category caps turn a passive log
into something that tells you when to stop. Meter fill carries severity
(blue → amber at 90% → red over cap), the track is a lighter step of the same
hue, and an over-cap row gets an **icon plus a label** — never color alone.

**Comparison is the point.** Every number gets a "vs previous period." A total
with no baseline is trivia.

**Editing happens in place.** A drawer or modal — never a page navigation that
drops your filters.

**Charts accessible by construction.** 2px lines; bars ≤24px with a 4px rounded
data-end, square at the baseline; hairline *solid* gridlines one step off the
surface; 10%-opacity area washes; a legend whenever there are ≥2 series; exactly
one direct label at the line end; a crosshair + tooltip on every plot; and a
`<details>` table view of the same data so nothing is gated behind hover.

**Palette is validated, not eyeballed.** The two-series pair
(`#3987e5` / `#d95926`) was run through a CVD validator against the mockup's
actual surface color: worst-pair ΔE 26.8 (protan) against a target of ≥8, and
all six checks — lightness band, chroma floor, CVD separation, normal-vision
floor, contrast — pass.

---

## 3. Token mapping

The mockup uses CSS custom properties instead of Tailwind classes so it renders
with zero dependencies. The `:root` block *is* the Tailwind config:

```js
tailwind.config = {
  darkMode: "class",
  theme: { extend: { colors: {
    page:    "#0c0e13",   // was slate-900 — now distinct from cards
    surface: "#14171f",   // card background
    well:    "#1a1e28",   // inputs, segmented controls
    hair:    "#242935",   // all borders
    ink:     "#f2f3f5",   // primary text
    ink2:    "#a9b0bd",   // secondary text
    muted:   "#7a8291",   // axis labels, captions
    brand:   { DEFAULT: "#3987e5", hover: "#4d95ea", soft: "rgba(57,135,229,.14)" },
    series2: "#d95926",   // "previous period" in comparisons
    good:    "#0ca30c", warn: "#fab219", crit: "#d03b3b",
  }}},
};
```

Then: `bg-page` on `<body>`, `bg-surface border-hair` on cards, `text-ink2` for
labels, `bg-brand text-white` for primary buttons (**not** `bg-brand/20`).

If you keep Chart.js rather than porting the mockup's SVG code, the options that
matter: `borderWidth: 2`, `pointRadius: 0` with `pointHoverRadius: 5` and a 2px
surface-colored `pointHoverBorderColor`, `borderRadius: 4` +
`borderSkipped: 'bottom'` on bars, `barThickness` capped at 24, grid color one
step off the surface, `interaction: { mode: 'index', intersect: false }`, and
explicit series colors from the palette above — never Chart.js defaults.

---

## 4. What this asks of `app.py`

Nothing needs a rewrite. Roughly in order of payoff:

1. **Previous-period totals.** Run the same filtered query shifted back by the
   range length. Unlocks every delta badge. ~10 lines reusing
   `apply_expense_filters`.
2. **A `Budget` model** — `(category, amount, month)` — plus a `budget_used`
   computation. Unlocks the meters, the "needs attention" list, and the
   month-end projection. This is the second model `PLAN.md` says would justify
   an app factory; that's the moment to make the split.
3. **A `recurring` flag on `Expense`**, or detection by `(description, amount)`
   repeating month over month. Unlocks the fixed/variable split.
4. **Make `export_csv` share `index`'s filtering** — the
   `category.in_(CATEGORIES)` fallback and the `end < start` guard. Already in
   the backlog; under "one filter row scopes everything" it becomes a
   correctness issue, not a nicety.
5. **Preserve active filters on redirect** after add / edit / delete. Also
   already in the backlog.
6. **Fix the Reset link** to `url_for('index')`.
7. **A JSON endpoint** (`POST /api/expense/<id>`) if editing moves to a drawer
   rather than a page.

---

## 5. Known gaps in the mockup

Deliberately not built, so it's clear what isn't being specified:

- 12 table rows, one page of data; no pagination, sorting, or search results
- Buttons and chips are inert — nothing is wired up
- No responsive work below ~1100px beyond a single-column collapse
- No empty, loading, or error states
- No `:focus-visible` pass (fields have focus rings; nothing else does)
- Sidebar "saved views" are a proposal, not a spec
- Demo data is invented, though it uses the real `CATEGORIES` and `Expense` shape
