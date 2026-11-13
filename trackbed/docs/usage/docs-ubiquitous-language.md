# docs:ubiquitous-language

Use it when a conversation has surfaced domain terms your team uses without a shared definition, uses one word for two concepts, or uses two words for one. It extracts those terms from the current conversation into a glossary at `UBIQUITOUS_LANGUAGE.md` in the repository root, picks one canonical term per concept, and flags the ambiguous ones. It writes or updates that file, and shows you what it plans before it does. It is not for general programming vocabulary or code-level type glossaries; to name and scope a single feature, use `trackbed:docs:feature-spec`.

## Before you run it

- The conversation already contains domain terms. With none, the skill stops and asks for three to five example terms or a description of the project's subject area.

## Examples

```text
# Build the glossary from the domain terms used in this conversation
/trackbed:docs:ubiquitous-language

# Run it again later to merge new terms into the existing glossary
/trackbed:docs:ubiquitous-language
```

## What you get

- `UBIQUITOUS_LANGUAGE.md` at the repository root: a table of terms, each with a one-sentence definition and the aliases to avoid, grouped by subdomain when the terms cluster. It also holds the relationships between terms, an example dialogue that uses them, and the flagged ambiguities with a proposed resolution for each.
- For a new glossary, the target path and an outline of the terms first. The file is written after you confirm.
- For an existing glossary, a merge instead of an overwrite: the skill lists the terms it adds and the definitions it updates before writing, and asks before it renames a term already in the file, splits a section, or drops terms.
- A note on domain terms it found in the code or docs but not in the conversation. It does not add them.

If the project has a `GLOSSARY.md` instead, the skill asks whether to migrate it or keep that file name.
