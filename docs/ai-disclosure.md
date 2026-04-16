# AI Disclosure and Wikifunctions Norms

Reference doc summarizing the rules, discussions, and community norms around using AI tools to contribute to Wikifunctions. Last updated 2026-04-15.

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
