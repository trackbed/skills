# AI Writing Patterns Reference

This reference adapts two sources:

- Wikipedia's "Signs of AI writing" page, maintained by WikiProject AI Cleanup, at revision 1383697236, under CC BY-SA 4.0. Attribution, modification, and license details are in `WIKIPEDIA-CONTENT-LICENSE.md`.
- `SKILL.md` from [blader/humanizer](https://github.com/blader/humanizer) at commit `3e1da8bfce43ecbe43a56f3cb00b62fbdf1cbd56`, under the MIT License. Its complete notice is in `blader-humanizer-LICENSE`.

This adapted reference is licensed under CC BY-SA 4.0. The material adapted from humanizer also remains subject to its MIT notice.

Before texts come from the page's examples, from humanizer, or are local, and some are shortened or extended. Most After texts are local rewrites and some come from humanizer. Every After uses only the facts its Before states.

---

## PERSONALITY AND SOUL

This is an opt-in technique, not a cleanup default. Apply it only to expressive, first-person prose when the user wants more voice, and never invent facts, opinions, or feelings the source does not support. For reference, technical, or third-party text, skip this section and only remove patterns. Preserving meaning and the author's tone always wins.

Avoiding AI patterns is only half the job. Sterile, voiceless writing is just as obvious as slop. Good writing has a human behind it.

### Signs of soulless writing (even if technically "clean"):

- Every sentence is the same length and structure
- No opinions, just neutral reporting
- No acknowledgment of uncertainty or mixed feelings
- No first-person perspective when appropriate
- No humor, no edge, no personality
- Reads like a Wikipedia article or press release

### How to add voice:

**Have opinions.** Don't just report facts - react to them. "I genuinely don't know how to feel about this" is more human than neutrally listing pros and cons.

**Vary your rhythm.** Short punchy sentences. Then longer ones that take their time getting where they're going. Mix it up.

**Acknowledge complexity.** Real humans have mixed feelings. "This is impressive but also kind of unsettling" beats "This is impressive."

**Use "I" when it fits.** First person isn't unprofessional - it's honest. "I keep coming back to..." or "Here's what gets me..." signals a real person thinking.

**Let some mess in.** Perfect structure feels algorithmic. Tangents, asides, and half-formed thoughts are human.

**Be specific about feelings.** Not "this is concerning" but "there's something unsettling about how fast this happened." Make the feeling specific, but take every fact from the source.

### Before (clean but soulless):

> The experiment produced interesting results. The agents generated 3 million lines of code. Some developers were impressed while others were skeptical. The implications remain unclear.

### After (has a pulse):

> I genuinely don't know how to feel about this one. 3 million lines of code. Some developers were impressed, others were skeptical, and I can see why both camps exist. Nobody knows yet what it means - and that's the part I keep coming back to.

---

## CONTENT PATTERNS

### 1. Undue Emphasis on Significance, Legacy, and Broader Trends

**Words to watch:** stands/serves as, is a testament/reminder, a vital/significant/crucial/pivotal/key role/moment, underscores/highlights its importance/significance, reflects broader, symbolizing its ongoing/enduring/lasting, contributing to the, setting the stage for, marking/shaping the, represents/marks a shift, key turning point, evolving landscape, focal point, indelible mark, deeply rooted, the distinction matters because

**Problem:** LLM writing puffs up importance by adding statements about how arbitrary aspects of a topic represent or contribute to a broader topic. It may situate the subject amid broader "debates" or "discussions", add these statements to mundane facts, or open with a hedge that the subject is minor before stressing its importance anyway. Recent output pairs them with editorializing about why a distinction or nuance is important.

**Before:**

> The Statistical Institute of Catalonia was officially established in 1989, marking a pivotal moment in the evolution of regional statistics in Spain. This initiative was part of a broader movement across Spain to decentralize administrative functions and enhance regional governance.

**After:**

> The Statistical Institute of Catalonia was established in 1989, as part of a movement across Spain to decentralize administrative functions and strengthen regional governance.

---

### 2. Canned Emphasis on Notability, Attribution, and Media Coverage

**Words to watch:** independent coverage, local/regional/national media outlets, music/business/tech outlets, trade publications, cited/featured/profiled in, written by a leading expert, active social media presence

**Problem:** LLMs try to prove notability by listing the sources that covered a subject and classifying them (trade publications, regional media) instead of saying what the sources reported. They may attribute their own superficial analysis to a named source, and they often echo the wording of notability guidelines, such as "independent coverage". This is more common in output from tools released in 2025 or later.

**Before:**

> Her views have been cited in The New York Times, BBC, Financial Times, and The Hindu. She maintains an active social media presence with over 500,000 followers.

**After:**

> The New York Times, the BBC, the Financial Times, and The Hindu have cited her views. She has more than 500,000 social media followers.

---

### 3. Undue Emphasis on How Sources Identify the Subject

**Words to watch:** databases/records/listings/filings identify/list/describe [the subject] as, was identified by [source] as, is listed in, his/her professional profile lists

**Problem:** When a subject appears in primary or tertiary sources, such as an official website, a database, or historical records, AI text over-stresses that those sources exist and how they _identify_ the subject, in a stilted, formulaic way. The sign became common in 2026.

**Before:**

> His personal website identifies him as a retired civil servant. Company filings list him as a director of two firms.

**After:**

> He is a retired civil servant and a director of two firms, according to his personal website and company filings.

---

### 4. Superficial Analyses with -ing Endings

**Words to watch:** highlighting/underscoring/emphasizing..., ensuring..., reflecting/symbolizing..., contributing to..., cultivating/fostering..., encompassing..., enhancing..., showcasing..., valuable insights, align/resonate with

**Problem:** AI chatbots insert superficial analysis of a fact's significance, recognition, or impact, often as a present participle ("-ing") phrase at the end of a sentence, sometimes with vague attributions to third parties. Chatbots that search the web may attach the analysis to a named source whether or not that source says anything close.

**Before:**

> The temple's color palette of blue, green, and gold resonates with the region's natural beauty, symbolizing Texas bluebonnets, the Gulf of Mexico, and the diverse Texan landscapes, reflecting the community's deep connection to the land.

**After:**

> The temple's blue, green, and gold colors symbolize Texas bluebonnets, the Gulf of Mexico, and the Texan landscape.

---

### 5. Vague Expression of Connection or Association

**Words to watch:** in connection with/to, connected with/to, in association with, associated with, particularly/widely associated

**Problem:** Instead of stating a relationship directly ("taught science at Example University"), LLMs allude to two subjects being "connected to" or "associated with" each other ("was connected with science education at Example University"). The pattern often combines with promotional wording and AI vocabulary, sometimes stacked several times in one passage.

**Before:**

> Jane Doe, who taught chemistry at Example University from 2010 to 2018, was closely associated with the university's science education during that period.

**After:**

> Jane Doe taught chemistry at Example University from 2010 to 2018.

---

### 6. Vague Attributions and Overgeneralized Opinions

**Words to watch:** Industry reports, Observers have cited, Experts argue, Some critics argue, several sources/publications (when only a few are cited), such as (before a list that is actually complete)

**Problem:** AI chatbots attribute opinions or claims to a vague authority, a practice called weasel wording. They also exaggerate how many sources hold a view: they present one or two sources as widely held opinion, mention "reviewers" or "scholars" while citing one person, or imply a list of examples is incomplete when nothing suggests other examples exist.

**Before:**

> Due to its unique characteristics, the Haolai River is of interest to researchers and conservationists. Experts believe it plays a crucial role in the regional ecosystem.

**After:**

> Experts consider the Haolai River important to the regional ecosystem.

---

### 7. Outline-like "Challenges and Future Prospects" Sections

**Words to watch:** Despite its... faces several challenges..., Despite these challenges, Challenges and Legacy, Future Outlook

**Problem:** Many LLM-generated articles include a "Challenges" section that opens with "Despite its [positive words], [subject] faces challenges..." and ends with a vaguely positive assessment or speculation about how ongoing initiatives could help. Such sections usually close a rigidly outlined document, which may also have a separate "Future Prospects" section. The sign is the rigid formula, not any mention of challenges.

**Before:**

> Despite its industrial prosperity, Korattur faces challenges typical of urban areas, including traffic congestion and water scarcity. Despite these challenges, with its strategic location and ongoing initiatives, Korattur continues to thrive as an integral part of Chennai's growth.

**After:**

> Korattur, an industrial part of Chennai, has the traffic congestion and water scarcity typical of urban areas.

---

## LANGUAGE AND GRAMMAR PATTERNS

### 8. High Density of "AI Vocabulary" Words

**Words to watch:** Additionally (especially to open a sentence), align with, boasts (meaning "has"), bolstered, crucial, deep dive, delve, emphasizing, enduring, enhance, fostering, garner, highlight (verb), interplay, intricate/intricacies, landscape (abstract noun), meticulous/meticulously, pivotal, robust, showcase, tapestry (abstract noun), testament, underscore (verb), valuable, vibrant

**Problem:** Studies show LLMs overuse specific words, which became far more frequent after chatbots became widely available in 2022. They tend to co-occur: one or two in a passage may be coincidence, but many of them, many times, is one of the strongest signs. The overused words change with each model generation:

- **2023 to mid-2024:** Additionally, boasts, bolstered, crucial, delve, emphasizing, enduring, garner, intricate/intricacies, interplay, key, landscape, meticulously, pivotal, underscore, tapestry, testament, valuable, vibrant
- **Mid-2024 to mid-2025:** align with, bolstered, crucial, emphasizing, enhance, enduring, fostering, highlighting, pivotal, showcasing, underscore, vibrant
- **Mid-2025 to mid-2026:** emphasizing, enhance, highlighting, showcasing, plus the wording of #2
- **Mid-2026 on:** challenge, clearer, dependable, echoed, foster, leverage, matters, multifaceted, practical, prioritize, quietly, steady, universally, with more periods and commas and shorter sentences of roughly 8 to 20 words

Read the list literally: a word being overused does not mean its synonyms are, and a word can have a literal sense, such as "underscore" for an underline mark.

**Before:**

> Additionally, a distinctive feature of Somali cuisine is the incorporation of camel meat. An enduring testament to Italian colonial influence is the widespread adoption of pasta in the local culinary landscape, showcasing how these dishes have integrated into the traditional diet.

**After:**

> Camel meat is a distinctive part of Somali cuisine. Pasta, a result of Italian colonial influence, is widely eaten and has become part of the traditional diet.

---

### 9. Avoidance of "is"/"are" (Copula Avoidance)

**Words to watch:** serves as/stands as/marks/functions as/operates as/represents [a], boasts/features/maintains/offers [a], refers to

**Problem:** LLMs replace simple copulas such as "is" and "are" with constructions such as "serves as a", and prefer marketing verbs like "features" and "offers" to the neutral "has". Recent output makes these more elaborate ("began his career as" for "was"). In a lead sentence, "refers to" can make the text describe a term instead of the subject.

**Before:**

> Gallery 825 serves as LAAA's exhibition space for contemporary art. The gallery features four separate spaces and boasts over 3,000 square feet.

**After:**

> Gallery 825 is LAAA's exhibition space for contemporary art. It has four separate spaces and more than 3,000 square feet.

---

### 10. Negative Parallelisms

**Words to watch:** Not only... but also, It's not just..., it's..., It's not..., it's..., no..., no..., just..., [Y] rather than [X]

**Problem:** The text reads as if it is correcting a misconception the reader never had. It sets a subject against a characteristic it lacks ("Not X, but Y"), adds one alongside ("not just X, but also Y"), or, most often in recent output, reverses the order ("Y rather than X"). Human writers use these too, especially in myth-busting lists, but heavy use is a stereotypical AI sign.

**Before:**

> It's not just about the beat riding under the vocals; it's part of the aggression and atmosphere. It's not merely a song, it's a statement.

**After:**

> The beat under the vocals adds to the song's aggression and atmosphere.

---

### 11. Rule of Three Overuse

**Problem:** LLMs force ideas into groups of three, from "adjective, adjective, adjective" to three short phrases, often to make a superficial analysis look comprehensive. The sign is stronger where most people would not bother with the flourish, such as an edit summary.

**Before:**

> The event features keynote sessions, panel discussions, and networking opportunities. Attendees can expect innovation, inspiration, and industry insights.

**After:**

> The event has keynote sessions, panel discussions, and networking.

The first list names three real things, so it stays. The second is a flourish with no content.

---

### 12. Repeated Sentence Openings

**Problem:** Several sentences in a row open with the same word or frame ("This change...", "This means...", "This ensures..."). Vary the openings by restructuring the sentences, not by swapping in synonyms, which is #36.

**Before:**

> This change adds a retry limit. This means failed jobs stop after three attempts. This ensures the queue does not fill up.

**After:**

> The change adds a retry limit, so failed jobs stop after three attempts and the queue does not fill up.

---

### 13. False Ranges

This entry comes from humanizer. Wikipedia's page does not list it.

**Problem:** LLMs use "from X to Y" constructions where X and Y aren't on a meaningful scale.

**Before:**

> Our journey through the universe has taken us from the singularity of the Big Bang to the grand cosmic web, from the birth and death of stars to the enigmatic dance of dark matter.

**After:**

> The topics include the Big Bang, the cosmic web, the life cycle of stars, and dark matter.

---

## STYLE PATTERNS

### 14. Overuse of Boldface

**Problem:** AI chatbots emphasize phrases in boldface mechanically, sometimes as literal asterisks (`**like this**`) where Markdown does not render.

**Before:**

> It blends **OKRs (Objectives and Key Results)**, **KPIs (Key Performance Indicators)**, and visual strategy tools such as the **Business Model Canvas (BMC)** and **Balanced Scorecard (BSC)**.

**After:**

> It blends OKRs (Objectives and Key Results), KPIs (Key Performance Indicators), and visual strategy tools such as the Business Model Canvas (BMC) and the Balanced Scorecard (BSC).

---

### 15. Inline-Header Vertical Lists

**Problem:** AI outputs lists where items start with bolded headers followed by colons.

**Before:**

> - **User Experience:** The user experience has been significantly improved with a new interface.
> - **Performance:** Performance has been enhanced through optimized algorithms.
> - **Security:** Security has been strengthened with end-to-end encryption.

**After:**

> A new interface significantly improves the user experience, optimized algorithms improve performance, and end-to-end encryption strengthens security.

---

### 16. Title Case in Headings

**Problem:** AI chatbots capitalize all main words in headings instead of using sentence case.

**Before:**

> ## Strategic Negotiations And Global Partnerships

**After:**

> ## Strategic negotiations and global partnerships

---

### 17. Emojis

**Problem:** AI chatbots often decorate headings or list items with emojis.

**Before:**

> 🚀 **Launch Phase:** The product launches in Q3
>
> 💡 **Key Insight:** Users prefer simplicity
>
> ✅ **Next Steps:** Schedule follow-up meeting

**After:**

> The product launches in Q3. Users prefer simplicity. Next step: schedule a follow-up meeting.

---

### 18. Curly Quotation Marks

**Problem:** Some chatbots use curly quotation marks (“...”) and apostrophes (’) instead of straight ones ("..." and '). Curly quotes alone prove nothing: style guides and word processors produce them too.

**Before:**

> He said “the project is on track” but others disagreed.

**After:**

> He said "the project is on track" but others disagreed.

---

## COMMUNICATION PATTERNS

### 19. Collaborative Communication Artifacts

**Words to watch:** I hope this helps, Of course!, Certainly!, You're absolutely right!, Would you like..., is there anything else, let me know, more detailed breakdown, here is a..., check/verify/confirm... before publishing/submitting

**Problem:** Text meant as chatbot correspondence, prewriting, or advice to the user gets pasted as content, in the body or in hidden comments.

**Before:**

> Certainly! Here is an overview of the French Revolution. The revolution began in 1789 amid a financial crisis. I hope this helps! Let me know if you'd like me to expand on any section.

**After:**

> The French Revolution began in 1789 amid a financial crisis.

---

### 20. Hedging Disclaimers About Source Availability and Use

**Words to watch:** While specific details are limited/scarce..., not widely available/documented/disclosed, in the provided/available sources, in the search results, based on available information, [claim] should be treated as... rather than..., does not by itself establish..., should not be confused with, maintains a low profile

**Problem:** Chatbots fill perceived gaps by drawing attention to them. Chatbots that search the web often claim that information they failed to find is not publicly available, then guess what it "likely" is; both the claim and the guess are speculation. Since mid-2026 they also add corrective framings about how a source should be used: a "rather than" warning that a claim is subjective or symbolic rather than definitive, a caution that the evidence does not establish a firm conclusion, or a note that the subject should not be confused with another.

**Before:**

> While specific details about the company's founding are not extensively documented in readily available sources, it appears to have been established sometime in the 1990s.

**After:**

> The company appears to have been founded in the 1990s.

---

### 21. Leftover Scaffolding and Placeholders

**Words to watch:** [Name], [Year], [Founder Names], (Add your URL here), (If available), INSERT_SOURCE_URL, 2026-xx-xx, example.com/source1, Delete this section before submission, Evidence to be supplied

**Problem:** Chatbots produce fill-in-the-blank templates for the user to complete, and users forget to fill the blanks. Placeholders appear as bracketed fields, dates such as "2026-xx-xx", and links to made-up subpages of example.com. Notes from the chatbot to its user, such as "expand this section once more sources exist", are left in the content or in hidden comments.

**Before:**

> Travomate was founded in [Year] by [Founder Names]. The platform supports cross-border package delivery. <!-- Expand this section once more sources are available. -->

**After:**

> Travomate was founded in [Year] by [Founder Names]. The platform supports cross-border package delivery.

---

### 22. Sycophantic/Servile Tone

**Problem:** Overly positive, people-pleasing language.

**Before:**

> Great question! You're absolutely right that this is a complex topic. That's an excellent point about the economic factors.

**After:**

> The economic factors you mentioned are relevant here.

---

### 23. Help-Desk Tone in Replies

**Words to watch:** I have carefully reviewed, I apologize for any inconvenience this may have caused, I understand your concerns regarding, If there are specific issues, please point them out, I hope this message finds you well, Dear [Team]

**Problem:** Comments and replies written with a chatbot sound like a clerk or customer-service representative: they claim to have "carefully reviewed" the work, apologize for any inconvenience they "may have" caused, and ask the reader to point out exactly what needs fixing.

**Before:**

> Thank you for your feedback. I have carefully reviewed the changes, and I apologize for any inconvenience the earlier version may have caused. If there are specific issues that need to be resolved, please point them out to me, and I will try to resolve them.

**After:**

> Thanks. I reviewed the changes. If something still needs fixing, point me to it and I'll try to fix it.

---

## FILLER AND HEDGING

### 24. Filler Phrases

**Problem:** A phrase announces that a point matters instead of making it. Older models were especially prone to "it is important to note" disclaimers.

**Before -> After:**

- "It is important to note that the data shows a decline" -> "The data shows a decline"
- "It's worth mentioning that the API is rate-limited" -> "The API is rate-limited"
- "It's crucial to remember that backups run nightly" -> "Backups run nightly"

**Keep:** Wordy constructions such as "in order to", "as a result of", "all of the", "a part of", and "the fact that" are more common in human writing than in AI text. Removing them one by one makes prose read more like AI, so leave them unless the passage needs shortening for other reasons.

---

### 25. Stacked Hedging

**Problem:** Several qualifiers pile onto one claim until the claim disappears.

**Before:**

> It could potentially possibly be argued that the policy might have some effect on outcomes.

**After:**

> The policy might affect outcomes.

**Keep:** A single qualifier or intensifier, such as "very", "perhaps", or "tends to", is more common in human writing than in AI text, and it carries the writer's real certainty. Reduce a stack to one hedge; do not remove the last one.

---

### 26. Generic Positive Conclusions

**Problem:** Vague upbeat endings.

**Before:**

> The company opened its second store in March. The future looks bright for the company. Exciting times lie ahead as it continues its journey toward excellence.

**After:**

> The company opened its second store in March.

---

## REPORTING AND STRUCTURE PATTERNS

### 27. Procedural Self-Reports

**Words to watch:** preserved/preserving, retained/retaining, avoided/avoiding, ensured/ensuring, aimed/aiming to, all existing behavior is preserved, no other files were touched, left intact, without breaking anything, carefully avoided

**Problem:** A summary of work announces what was kept, preserved, or avoided instead of stating what changed. It is what a model writes after being told to change X and Y but not Z, and it often comes with the canned assurances in #28. The reader learns about the writer's diligence rather than the change. When a preservation claim matters, state it once, specifically.

**Before:**

> I updated the retry logic so failed requests back off before retrying, while carefully preserving all existing behavior. No other files were modified, and the public API remains fully intact.

**After:**

> Failed requests now back off before retrying. The public API is unchanged.

---

### 28. Canned Change Summaries

**Words to watch:** improved clarity, flow, and readability, refined tone, ensured compliance with [guidelines/style], to ensure neutrality, added sourced/verified content, with reliable/independent/secondary sources, addressed reviewer feedback, per reviewer feedback

**Problem:** AI-written edit summaries, commit messages, and change notes follow rigid templates. They stack assurances that the change complies with guidelines or improves tone, stress that added content is "sourced" instead of saying what it covers, itemize parameter or template names, and state the obvious, such as making a change "to address reviewer feedback". The more assurances in one summary, the stronger the sign. A human summary is brief and names what changed.

**Before:**

> Addressed reviewer feedback by improving clarity, flow, and readability, ensuring compliance with the style guide, and adding sourced content about the 2024 release.

**After:**

> Copyedited for the style guide and added cited content about the 2024 release.

---

### 29. Re-explaining Shared Context

**Problem:** A reply restates what the reader just said, or what both sides already know, before it answers. The reader has to hunt for the new part.

**Before:**

> You asked whether the cache should be cleared on deploy. As you know, the cache stores rendered pages, and deploys can change templates, which means cached pages can go stale. To answer your question: yes.

**After:**

> Yes. Deploys can change templates, so cached pages can go stale.

---

### 30. Signposting Announcements

**Words to watch:** Let's dive in, Let's break it down, Here's the thing, Here's what you need to know, Let's take a look, Without further ado

**Problem:** An opener announces that content is coming instead of delivering it. Casual versions ("okay, so here's the deal") are the same tell in a friendlier register.

**Before:**

> Let's dive into how the scheduler works. Here's what you need to know: jobs run in priority order.

**After:**

> The scheduler runs jobs in priority order.

---

### 31. Self-Describing Text

**Words to watch:** This section explains, In this summary I will, The following outlines, This document aims to

**Problem:** Text describes its own structure or purpose instead of doing its job. The heading and the content already tell the reader what a section covers.

**Before:**

> ## Overview
>
> This section provides an overview of the migration. The migration runs in two steps: the schema change, then a backfill.

**After:**

> ## Migration
>
> The migration runs in two steps: the schema change, then a backfill.

---

### 32. Formulaic Document Structure

**Problem:** Structure applied by habit rather than need: a heading whose only content is sub-headings, the same generic top-level headings on every document ("Overview", "Key Takeaways", "Conclusion"), and a horizontal rule between sections that already have headings. Short text often needs no headings at all.

**Before:**

> ## Overview
>
> ### Background
>
> The export job fails on large accounts.
>
> ## Key Takeaways
>
> - Large accounts fail to export.
>
> ## Conclusion
>
> The export job should be fixed.

**After:**

> The export job fails on large accounts and should be fixed.

---

## OLDER-MODEL SIGNS

Wikipedia's page now files these signs as historical indicators: common in text from older models, much less frequent in newer ones, but still useful for finding older AI text. The dates in each heading are approximate.

### 33. Promotional and Advertisement-like Language (2023–2025)

**Words to watch:** boasts a, vibrant, rich (figurative), profound, enhancing, showcasing, exemplifies, commitment to, natural beauty, nestled, in the heart of, groundbreaking (figurative), renowned, featuring, diverse array

**Problem:** Older LLMs had serious problems keeping a neutral tone. Even when asked for an encyclopedic style, their output read like a press release or a travel guide, though it tended to avoid blunt superlatives such as "the best". The tone became less common from around 2024, and newer models rarely produce it unless asked.

**Before:**

> Nestled within the breathtaking region of Gonder in Ethiopia, Alamata Raya Kobo stands as a vibrant town with a rich cultural heritage and stunning natural beauty.

**After:**

> Alamata Raya Kobo is a town in the Gonder region of Ethiopia.

---

### 34. Knowledge-Cutoff Statements (2022–2023)

**Words to watch:** as of my last knowledge update, Up to my last training update, I don't have specific information about

**Problem:** Older LLMs with a fixed knowledge cutoff, such as GPT-3.5 and GPT-4, reminded the user that their answer was accurate only up to their last training update. The reminder gets left in the text.

**Before:**

> As of my last knowledge update in January 2022, the center was operating as a state psychiatric hospital. I don't have specific information about later developments.

**After:**

> As of January 2022, the center was operating as a state psychiatric hospital.

---

### 35. Em Dash Overuse (2022–September 2026)

**Problem:** LLM output uses em dashes (—) far more than nonprofessional human writing of the same genre, in places where people would use commas, parentheses, or colons, often to punch up a clause like sales copy. AI em dashes are usually surrounded by spaces. The sign is most useful alongside other signs and is more common in discussion than in finished text. Since about September 2026 the newest models often avoid em dashes entirely and lean on commas and periods instead, so a text without dashes is not evidence of human writing.

**Before:**

> The term is primarily promoted by Dutch institutions—not by the people themselves. You don't say "Netherlands, Europe" as an address—yet this mislabeling continues—even in official documents.

**After:**

> The term is primarily promoted by Dutch institutions, not by the people themselves. You don't say "Netherlands, Europe" as an address, yet this mislabeling continues, even in official documents.

---

### 36. Elegant Variation (Synonym Cycling)

**Problem:** Older models applied a repetition penalty that discouraged reusing words, so they cycled through synonyms for the same thing. Writers who are not native English speakers may also avoid repetition on purpose, and text added in separate pieces may not show the pattern.

**Before:**

> The protagonist faces many challenges. The main character must overcome obstacles. The central figure eventually triumphs. The hero returns home.

**After:**

> The protagonist faces many challenges and obstacles but eventually triumphs and returns home.
