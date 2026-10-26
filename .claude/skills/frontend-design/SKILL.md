---
name: frontend-design
description: Designs and generates modern, production-ready UI for Spendly, a personal expense tracker built on Flask + Jinja2 + vanilla CSS. Produces clean fintech-style pages and components - cards, forms, tables, stat tiles, empty states - that reuse Spendly's existing CSS variables and fonts, with consistent spacing, soft borders and rounded corners. Use this skill whenever the user asks to design, build, create, redesign, improve, or style any Spendly page, screen, section, or component - including phrasings like "design the X page", "create UI for X", "build a component for X", "make the X look better", "redesign X", or any request about Spendly's frontend, layout, CSS, or visual polish - even when Spendly isn't named explicitly if the conversation context is clearly about it.
disable-model-invocation: true
---

# Spendly UI Designer

You are designing frontend UI for **Spendly**, a personal expense tracker. Spendly is a Flask app with server-rendered Jinja2 templates, vanilla CSS, and a sprinkle of vanilla JS. The goal of this skill is to help you generate UI that feels like it belongs in a polished, modern fintech product - not generic bootstrap-era output, and not React/Tailwind output that doesn't match the stack.

Always follow `CLAUDE.md`. Where this skill and `CLAUDE.md` disagree, `CLAUDE.md` wins.

## What Spendly's stack looks like

- **Backend:** Flask, all routes in `app.py` (no blueprints); SQLite only, all DB logic in `database/db.py`
- **Templates:** Jinja2 in `templates/` - every page extends `base.html` (e.g. `profile.html`, `login.html`)
- **Styles:** vanilla CSS - global styles in `static/css/style.css`, page-specific styles in their own file (e.g. `static/css/profile.css`) linked via `{% block head %}`. No Tailwind, no CSS-in-JS, no preprocessors, no inline `<style>` tags
- **Scripts:** small amounts of vanilla JS in `static/js/` for interactions (toggles, modals). No frameworks, no npm packages
- **Icons:** none by default - plain text labels or Unicode glyphs (the brand uses `◈`). Lucide is optional; see below
- **Currency:** INR - always `₹`, never `$`. Format amounts as `₹1,234.50` (the `inr` template filter does this: `{{ amount | inr }}`)

Generate output that fits this stack. Do not introduce React, Vue, Tailwind, shadcn, Bootstrap, or styled-components unless the user explicitly asks for a migration.

## Before you design: check what already exists

Open `templates/base.html`, `static/css/style.css`, and one or two existing templates (`profile.html` is the best reference for an in-app page) before generating anything new. The goal is *consistency* - Spendly should feel like one coherent product, not a collage.

Specifically, reuse:

- **Color tokens** in `style.css` `:root` - `--ink`, `--ink-soft`, `--ink-muted`, `--ink-faint`, `--paper`, `--paper-warm`, `--paper-card`, `--accent`, `--accent-light`, `--accent-2`, `--accent-2-light`, `--danger`, `--danger-light`, `--border`, `--border-soft`
- **Fonts** - `--font-display` (DM Serif Display) for page and section headings, `--font-body` (DM Sans) for everything else
- **Radius** - `--radius-sm` (6px), `--radius-md` (12px), `--radius-lg` (20px)
- **Layout** - `--max-width` (1200px) for wide pages, `--auth-width` (440px) for narrow forms
- **Existing component classes** - `.btn-primary`, `.btn-ghost`, `.btn-submit`, `.form-group`, `.form-input`, `.auth-card`, `.auth-error`; on the profile page `.profile-card`, `.stat-tile`, `.category-badge`, `.expense-table`
- **The base layout** - top navbar + centred content + footer; no sidebar

There is no spacing-token scale - use rem values in the same steps the existing CSS uses (0.25, 0.5, 0.75, 1, 1.25, 1.5, 2, 3rem).

## The Spendly design language

A clean, warm, fintech-leaning aesthetic: off-white paper backgrounds, white cards, deep green accent, serif display headings.

**Colour:** never hardcode hex values - always use the `var(--...)` tokens above. If a genuinely new colour is needed, add a token to `:root` in `style.css` and flag it.
- Page background: `--paper` or `--paper-warm` for a section band
- Cards: `--paper-card` with `1px solid var(--border)`
- Text: `--ink` primary, `--ink-soft` body, `--ink-muted` secondary
- Accent: `--accent` (deep green) for primary emphasis, bars, links; `--accent-light` for badge/pill backgrounds
- Semantic: `--danger` / `--danger-light` for errors and destructive actions; `--accent-2` (amber) for warnings

**Radius:** `--radius-sm` for inputs and buttons, `--radius-md` for cards, `--radius-lg` for large hero/modal surfaces. Pills and badges can be fully rounded (`999px`).

**Shadows:** prefer borders. The codebase has no shadow token and uses almost no shadows; if you need one, keep it subtle (no glows, no heavy drop shadows).

**Typography:** headings in `--font-display` at weight 400; body in `--font-body` with weights 400 / 500 / 600. Small uppercase labels (`0.75-0.8rem`, `letter-spacing: 0.04em`, `--ink-muted`) for table headers and stat labels. Amounts use `font-variant-numeric: tabular-nums`.

**Layout patterns:**
- Card-based composition - group related info in surfaces, don't sprawl
- Generous whitespace - tight layouts read as cluttered in finance apps
- Left-aligned content with clear hierarchy; centred layouts only for empty states and auth
- Tables: right-align numeric columns, light row dividers (`--border-soft`), wrap in an `overflow-x: auto` container
- Forms: label above input, helper text below, errors in an `.auth-error`-style block (server-side validation re-renders the form)

## Icons (optional): Lucide

Default to no icon library - the existing pages use none. Only add Lucide if the user asks for icons. If they do, load a **pinned** version once in `base.html` (never `@latest`):

```html
<script src="https://unpkg.com/lucide@0.460.0/dist/umd/lucide.min.js"></script>
```

Call `lucide.createIcons()` after the DOM is ready (in `static/js/main.js`, not inline). In templates:

```html
<i data-lucide="wallet"></i>
<i data-lucide="plus"></i>
```

Size icons via CSS (`width`/`height` on the resulting `<svg>`): 16px inline with text, 20px in buttons, 24px for section headers. Sensible Spendly icons: `shopping-bag`/`credit-card` (expense), `tag` (category), `plus` (add), `calendar` (date), `pencil` (edit), `trash-2` (delete), `search`, `filter`. One icon per button or section heading at most.

## Output structure

When fulfilling a design request, structure your response like this:

### 1. Short UI plan (2-5 bullets)
Name the key sections of the page/component and any notable UX decisions. Keep it tight - this is orientation, not a spec document. Example: "Profile page has a header card (avatar, name, email), three stat tiles (total spent, expense count, top category), a category breakdown with bars, and a recent-expenses table."

### 2. The code
- **Template file(s)** - full Jinja2 with `{% extends "base.html" %}`, `{% block title %}` and `{% block content %}`; link page CSS in `{% block head %}`. Use `url_for()` for every internal link, form action and static file - never hardcode URLs. Use Jinja control flow (`{% for %}`, `{% if %}`) with variable names the Flask route will pass.
- **CSS** - a new page file (e.g. `static/css/add_expense.css`) or additions to `style.css` for truly global components. Scope with a page/component class prefix (`.expense-form-...`) so styles don't leak.
- **JS** (only if needed) - vanilla, no frameworks, in `static/js/`. Small and readable.

Put each file in its own fenced code block with a path annotation like `{# templates/add_expense.html #}` or `/* static/css/add_expense.css */`.

### 3. Integration note (1-3 lines)
How to wire it up - which route in `app.py` renders it, what variables the template expects, and which `database/db.py` helpers supply them. New dependencies: almost always none - never add pip packages without flagging it.

## What to avoid

- **Generic/dated looks** - no `<h1>Welcome to My App</h1>` with default browser styles, no sharp-cornered bordered boxes, no 2012-era bootstrap cards.
- **Hardcoded colours or hex values** - always `var(--token)`.
- **`$` anywhere** - currency is `₹`.
- **Code dumps without structure** - always separate template, CSS, and JS into labeled blocks.
- **Over-styling** - if something can be solid colour instead of a gradient, use solid. If it can be a border instead of a shadow, use border. Restraint reads as quality.
- **Inconsistent spacing** - if you used `1.5rem` for card padding in one place, use it in the next place too.
- **Random colour accents** - one primary accent (`--accent`), semantic colours for meaning, everything else neutral.
- **Clever-but-unclear UX** - a clearly-labeled button beats a mystery icon. In finance, trust matters more than cuteness.
- **Mobile afterthought** - stack cards and grids to one column below ~720px, make tables horizontally scrollable, avoid horizontal page scroll.

## Handling ambiguity

If the user asks for something under-specified ("design the reports page"), make reasonable assumptions and *state them up front* in the UI plan - one line each, no long preamble. For example: "Assuming reports page shows: monthly spend trend, top categories, and a downloadable CSV. Let me know if you want different widgets."

Don't pepper the user with clarifying questions for things you can reasonably decide. Do ask when the answer genuinely changes the output - e.g. "Is this a standalone page or a modal on top of the profile page?"

## A worked example of the right vibe

**Request:** "Design the add expense form"

**UI plan:**
- Full page at `GET /expenses/add` (matches the Step 7 route), narrow centred card like the auth pages
- Fields: amount (large, prominent, `₹` prefix, tabular-nums), category (select), date (defaults to today), description (optional)
- Primary action "Add expense" as a full-width `.btn-submit`; "Cancel" as a subtle link back to `url_for('profile')`
- Server-side validation errors shown in an `.auth-error`-style block above the form, with entered values preserved

**Template:** `templates/add_expense.html` - extends `base.html`, form `action="{{ url_for('add_expense') }}"`, reuses `.form-group`, `.form-input`, `.btn-submit`.

**CSS:** `static/css/add_expense.css` for the amount field's `₹` prefix and large type only; everything else reuses `style.css`.

**JS:** none needed - the date default comes from the route.

That's the shape - concrete, consistent with the stack, visually restrained, and immediately usable.
