# AI Disclosure: Wikifunctions and Wikidata

Reference doc summarizing the rules, discussions, and community norms around using AI tools to contribute to Wikifunctions and (increasingly, as our work touches Wikidata) Wikidata. Last updated 2026-04-17.

## Current rules

All of the below are **drafts** — none have been formally adopted through a community vote. But they represent the active community expectations.

### Wikifunctions:Editing guidelines (draft, 2026-04-09)

The "Large language models" section says:

> Large language models (LLMs/AI) and other artificial intelligence tools that generate code are **permitted for use** in editing code on Wikifunctions. However, you should review the work of the AI, which the tests feature is recommended for. Users are responsible for the quality of AI-generated code, and poor quality code wastes the time of volunteer contributors. Users are *strongly* encouraged to declare their use of AI and what they used AI for in their edit summaries, as it may be beneficial to improving the project.

> AI agents **must not** edit autonomously (using tools like OpenClaw), per the bot policy.

The page's own framing: bolded **must** = binding policy; everything else = recommendations. So:
- AI-assisted code is explicitly **permitted** (bolded)
- Autonomous AI agents are explicitly **prohibited** (bolded "must not")
- Disclosure is "strongly encouraged" but not yet mandatory

### Wikifunctions:Bots (draft, 2025-09-11)

All bots require advance permission for specific listed tasks. Must run from separate accounts with "bot" in the username. Source code must be published under an OSI-approved open source license. No more than one edit per 5 seconds for non-urgent tasks. Operators are responsible for all bot actions and must be identifiable on the bot's user page.

### Meta: Artificial intelligence/Draft policy (draft, 2026-04-13)

A Wikimedia-wide draft proposes two tiers:

**Baseline policy** (proposed common ground): AI-generated content must be disclosed and human-reviewed. Editors take full responsibility.

**Opt-out policy** (default for projects without their own policy): AI-generated content is **prohibited** except for translation and basic copyediting.

Wikifunctions is not currently listed on Meta's policy-by-project tracker. If the opt-out policy is adopted before Wikifunctions formalizes its own guidelines, the stricter default could technically apply.

## Community discussions

### Disclosure incentives (Editing guidelines talk page, 2026-04-09)

LZia (WMF), a Wikimedia Foundation researcher, advocated for stronger disclosure norms, drawing on the ACM CHI 2026 conference's LLM policy:

> I encourage you to carefully consider if you want to leave the responsibility of making the decision whether to disclose or not to the editor. I wonder what can be the advantage of allowing the editor to make that decision vs stating the policy as clearly expecting editors to communicate their usage?

They recommended editors disclose **what specifically** they used AI for (writing code, getting feedback, detecting inconsistencies, etc.), not just that they used it. Reasons: helps the community learn good use cases, identify where AI does poorly, and provides "an opportunity for intentionality (and slow down) at the moment of publishing an edit."

The guidelines author (Feeglgeef) strengthened the language from "should consider declaring" to "strongly encouraged" in response, but stopped short of mandatory.

### Functioneer request scrutiny (2026-04)

A user applying for functioneer rights was initially challenged because "Grammarly flags your text as AI generated." After clarifying they used DeepL for grammar and an LLM for code formatting/linting, the community supported the request with the caveat: "Please do acknowledge and take care when using LLMs in your work."

Takeaway: the community is actively watching for AI use and values transparency. Undisclosed use creates friction; disclosed use is accepted.

### Abstract Wikipedia and AI (Project Chat, 2025-05)

Denny Vrandecic (project founder) explained why Abstract Wikipedia avoids LLMs for text generation (no correctness guarantees, poor for small languages) but envisions them for the input side — converting free text into abstract representations.

## Gaps and ambiguities

1. **Compositions aren't "code."** The guidelines address "editing code." Compositions (our primary output) are structured data, not code. Function definitions, test cases, labels, and type work are also not addressed. The spirit clearly covers all contributions, but the letter only says "code."

2. **AI-assisted design is unaddressed.** Using an AI to plan function decompositions, explore Wikidata modeling, or draft composition trees — then building them manually in the UI — is a qualitatively different workflow from having an AI write code. No discussion has touched on this.

3. **API-based editing by a human using AI tools** sits in a gray area between "human editing with AI assistance" (permitted) and "autonomous AI agent" (prohibited). The key distinction is human review and decision-making at each step.

## Our approach

This project uses Claude Code as a design partner and (potentially) an API editing tool, with the human (Ragesoss) reviewing and approving every edit. This fits within the current guidelines:

- **Human review:** Every function design is reviewed and approved before creation. Test cases are validated against known Wikidata values. The human decides what to build and when.
- **Not autonomous:** The AI does not edit Wikifunctions on its own. Even with API scripts, edits are initiated and reviewed by the human operator.
- **Disclosure:** Edit summaries from our API scripts should automatically disclose AI assistance and what it was used for.

### Edit summary format

When our scripts create or edit ZObjects via the API, they should include an edit summary like:

```
Created with AI assistance (Claude, function design and composition drafting)
```

The summary should indicate:
1. That AI was used
2. Which AI (Claude)
3. What the AI contributed (e.g., "function design and composition drafting", "test case generation", "Python implementation")

This follows the spirit of LZia's recommendation to disclose what specifically AI was used for, even though mandatory disclosure hasn't been adopted yet.

---

## Wikidata norms

Wikidata is a separate project from Wikifunctions, with separate (and more mature) policies. When our sessions lead to Wikidata edits — adding missing claims, fixing modelling gaps, correcting qualifiers — those edits are governed by Wikidata's rules, not Wikifunctions'. Summary of what applies.

### Wikidata:Bots (policy)

The policy's own definition draws the important line:

> Bots (also known as robots) are tools used to make edits **without the necessity of human decision-making**.

Bot accounts require (per [Wikidata:Bots](https://www.wikidata.org/wiki/Wikidata:Bots)):
- Separate account with "bot" in the username.
- Approval via [Wikidata:Requests for permissions/Bot](https://www.wikidata.org/wiki/Wikidata:Requests_for_permissions/Bot) — a test run of 50–250 edits before the flag is granted.
- Bot flag set on all edits; respect `maxlag`; settable max-edits-per-minute.
- Identified operator on the bot's user page; operator is responsible for cleanup.

Our workflow is explicitly **not** a bot under this definition: every edit is individually decided by the human operator (Ragesoss) — the AI drafts, the human reviews the proposed claim, the human clicks Save (or runs the QuickStatements / API call). Human decision-making is in the loop per edit.

### Wikidata:Requests for comment/Mass-editing policy (under discussion, 2026-04-14)

Proposed language defines mass editing as:

> changes [that] are made to existing entities or the addition of new entities without being reviewed individually by the person making the edits and which could not reasonably be done manually.

Our pattern explicitly fails both halves of that test — each edit is individually reviewed, and the batches are always small enough to do manually in principle. So we remain outside the mass-editing scope even if this RfC is adopted as written.

Note: the RfC is not yet adopted, has open opposition, and is likely to be revised. Re-check when the session picks up.

### LLM-specific policy on Wikidata

**There isn't one yet.** There is a [WikiProject Large Language Models](https://www.wikidata.org/wiki/Wikidata:WikiProject_Large_Language_Models) but its talk page makes clear the group is exploratory — tool projects (statement prediction, vandalism detection), no policy statements. No disclosure rule, no LLM-use restrictions.

Contrast [Wikipedia:Large language models](https://en.wikipedia.org/wiki/Wikipedia:Large_language_models) (different project, stricter): disclosure required, generation/rewriting of article content prohibited except for translation and basic copyediting. That policy does **not** apply to Wikidata — different project, different norms — but it's the most developed community thinking on LLM editing in the Wikimedia family and a likely template if/when Wikidata writes its own.

### Meta:Artificial intelligence/Draft policy

Cross-Wikimedia proposal (already summarised above for Wikifunctions) anticipates a baseline requiring disclosure and human review, with projects allowed to opt in to stricter rules. Wikidata is not listed on the policy-by-project tracker; if the opt-out default is adopted, Wikidata would get the stricter "prohibit-except-translation/copyedit" behaviour by default — which would block a lot of current practice, so an opt-in to the baseline is the likely outcome. But the proposal is draft.

### Rate limits / etiquette

Not formally policy for non-bot editors, but the standard expectation:

- Respect [`maxlag`](https://www.mediawiki.org/wiki/Manual:Maxlag_parameter) (stop when replag > 5 seconds).
- Follow [API:Etiquette](https://www.mediawiki.org/wiki/API:Etiquette) — serial requests, not parallel; reasonable delay between edits.
- QuickStatements' own UI throttles to roughly one edit every 3–5 seconds by default; that's a safe baseline for API-driven tooling too.

## Our approach on Wikidata

The summary version: treat Wikidata edits the same way we treat Wikifunctions edits — human-reviewed, per-edit decisions, disclosed — and add a Wikidata-flavoured disclosure string to edit summaries even though Wikidata itself doesn't currently require it.

### Why disclose on Wikidata if it's not required

1. Consistency with our Wikifunctions practice.
2. Forward-compatibility: the Meta baseline policy and ongoing community discussion both lean toward disclosure. Starting disclosed means nothing has to change when norms tighten.
3. The ACM CHI-style argument LZia made on Wikifunctions — "intentionality and slow down at the moment of publishing" — applies equally to Wikidata claims.
4. If a contribution is ever questioned, having "Created with AI assistance" in the summary is the difference between a conversation and an accusation.

### Edit summary format on Wikidata

For edits made through the Wikidata API, use an edit summary like:

```
Add relative-minor claim; Created with AI assistance (Claude, claim drafting and qualifier modelling research)
```

Same three elements as Wikifunctions — that AI was used, which AI, what it contributed — adapted to match what's actually being done at Wikidata (claim work, lexeme sense additions, qualifier fixes, etc.).

For QuickStatements batches, add `/* AI-assisted, Claude */` or similar to the batch summary field so the flag shows up in edit history.

### What stays a human-only call

- Deciding which data to add (what's missing, what's correct, what the source is).
- Reviewing each proposed edit before it goes through.
- Anything controversial or potentially contested — AI-drafted, but the human both reviews and is the one whose account goes on the edit.
- Bulk modelling changes that could affect many existing consumers (don't do these without opening a discussion first, per the mass-editing RfC spirit).
