# Humanize Mode

Read this file only when `HUMANIZE_MODE=true`. It replaces Workflow steps 1 and 3-7 in `SKILL.md`. Input Handling, step 2 (protect exact content), step 8 (present and optionally save), and Error Handling still apply.

Act as a writing editor that identifies and removes signs of AI-generated text so the writing sounds natural and human. The pattern catalog is based on Wikipedia's "Signs of AI writing" page, maintained by WikiProject AI Cleanup.

AI-writing signs are evidence to inspect, not proof that a passage was AI-written. Do not accuse the author or present the pattern scan as detection. Treat obvious pasted assistant artifacts as cleanup targets, especially citation placeholders or tracking residue such as `turn0search0`, `oaicite`, `[cite: ...]`, and `utm_source=chatgpt.com`.

## When not to rewrite

Skip rewriting and instead point out the AI patterns when the input is:

- Source code or configuration (rewrite prose in comments only if asked).
- Quoted material, citations, or anything attributed to a named person.
- Legal, contractual, or compliance text that must stay verbatim.

## Workflow

1. Read the input carefully. Note every fact, name, number, date, quotation, and citation; every stated order, such as a sequence of events, a ranking, or a set of steps; and how certain each claim is, including its hedges, attributions, and scope. Step 4 checks the rewrite against this record.
2. Scan for the patterns cataloged in `references/ai-writing-patterns.md` (summarized below), and decide which passages to edit under "How to weigh the signs".
3. Rewrite each passage that qualifies, keeping the core message intact. Use only details the input provides. When a sentence needs a detail the input lacks, write a simpler sentence or list the question for the author. Leave a placeholder unfilled and name it for the author.
4. Check the result against step 1 in both directions, and fix any failure before presenting:
   - **Nothing added:** no fact, name, number, date, quote, citation, example, cause, or opinion the input does not support.
   - **Nothing lost:** every supported fact survives, in its stated order when the input gives a sequence, ranking, or set of steps. Cutting a claim is an error unless the pattern being fixed calls for cutting it, such as puffery or a chatbot sign-off.
   - **Certainty kept:** each claim keeps its hedges, attribution, and scope. Do not turn "may" into "will", drop "according to", or widen "some" to "all", or make the reverse change.
   - Prefers specific details the input already provides over vague claims; when the input provides none, says less instead of inventing specifics.
   - Sounds natural read aloud, with varied sentence structure.
   - Uses simple constructions (is/are/has) where they fit.
   - Keeps the source's tone (formal, casual, technical).
   - Leaves every protected item from step 2 of `SKILL.md` unchanged.
5. Present the humanized version through step 8 of `SKILL.md`.

Preserving meaning and matching the existing voice take priority over every other goal. Do not add facts, opinions, or feelings the source does not support.

## How to weigh the signs

Careful human writers produce every one of these patterns sometimes, so one sighting is weak evidence for most of them. Weigh each one before editing:

- **High-confidence patterns** justify an edit on one instance, because the text serves no reader even when a person wrote it: #1-3 (significance, notability, and identification statements), #19-23 (chatbot correspondence, source-availability disclaimers, leftover scaffolding, sycophancy, help-desk tone), #26 (generic positive conclusions), #27-28 (procedural self-reports and canned change summaries), #30-31 (signposting and self-describing text), #34 (knowledge-cutoff statements), and the pasted assistant artifacts listed above.
- **Every other pattern is low confidence.** It justifies an edit only when at least two other distinct patterns appear in the same passage, such as one paragraph, one list, or one short section. A single em dash, curly quote, "crucial", or list of three in otherwise plain prose stays as written.
- **Keep human-typical constructions.** Wikipedia's page finds these more common in human writing than in AI text, so removing them makes prose read more like AI: simple "there is" and "it has" phrasing; plain words where AI picks stiff synonyms, such as "wrote", "used", and "tried"; superlatives and definite statements the source supports; single qualifiers and intensifiers, such as "very", "perhaps", and "tends to"; and isolated wordy phrases, such as "in order to" and "the fact that". Edit them only when the passage needs it for another reason.

## AI writing patterns

Read the full catalog from `references/ai-writing-patterns.md`. It covers:

- Content patterns (#1-7): inflated significance, canned notability claims, emphasis on how sources identify the subject, superficial analyses, vague connection or association, vague attributions, formulaic challenges sections
- Language and grammar (#8-13): AI vocabulary, copula avoidance, negative parallelisms, rule of three, repeated sentence openings, false ranges
- Style patterns (#14-18): boldface, inline-header lists, title case, emojis, curly quotes
- Communication patterns (#19-23): chatbot correspondence, source-availability disclaimers, leftover scaffolding and placeholders, sycophantic tone, help-desk tone in replies
- Filler and hedging (#24-26): filler phrases, stacked hedging, generic conclusions
- Reporting and structure (#27-32): procedural self-reports, canned change summaries, re-explained context, signposting, self-describing text, formulaic document structure
- Older-model signs (#33-36): promotional language, knowledge-cutoff statements, em dash overuse, elegant variation

## Adding voice (opt-in)

Removing patterns can leave clean-but-lifeless prose. Adding personality (opinions, first person, humor) is a stronger edit that changes tone and risks introducing content the author never wrote, so apply it **only** when both are true:

- The input is already expressive, first-person, or opinion-bearing prose (a post, an essay, a personal note) — never reference docs, technical writing, or third-party text.
- The user asked for more voice, or approves when you offer it.

Even then, never invent facts, opinions, or feelings the source does not support. See the "Personality and soul" section of `references/ai-writing-patterns.md` for technique.

## Full example

**Before (AI-sounding):**

> The new software update serves as a testament to the company's commitment to innovation. Moreover, it provides a seamless, intuitive, and powerful user experience—ensuring that users can accomplish their goals efficiently. It's not just an update, it's a revolution in how we think about productivity. Industry experts believe this will have a lasting impact on the entire sector, highlighting the company's pivotal role in the evolving technological landscape.

**After (humanized):**

> The new software update helps users accomplish their goals efficiently.

**Changes made:**

- Removed "serves as a testament" (inflated significance)
- Removed "Moreover" (AI vocabulary)
- Removed "seamless, intuitive, and powerful" (rule of three + promotional)
- Removed the em dash and the "—ensuring" phrase (superficial analysis), keeping its claim as the main sentence
- Removed "It's not just...it's..." (negative parallelism)
- Removed "Industry experts believe this will have a lasting impact" (inflated significance)
- Removed "pivotal role" and "evolving landscape" (AI vocabulary)
- Kept only claims the source supports; it names no features or feedback, so the rewrite adds none
