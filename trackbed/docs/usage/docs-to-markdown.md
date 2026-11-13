# docs:to-markdown

Use it to turn a file into Markdown the agent can read or analyze: PDF, Word, PowerPoint, Excel, Outlook messages, HTML, CSV, JSON, XML, images, audio, ZIP archives, EPubs, and YouTube URLs. It runs MarkItDown through `uvx`, so you do not install MarkItDown yourself. The skill has no flags of its own: name the file or URL and say in plain words where the result should go. The agent also uses it without the command when you ask it to convert a file.

## Before you run it

- `uv` is installed; it provides `uvx`. Without it, the skill can fall back to `pipx` or `pip`.
- For Azure Document Intelligence or Azure Content Understanding, an endpoint: in your request, or in `MARKITDOWN_DOCINTEL_ENDPOINT` or `MARKITDOWN_CU_ENDPOINT`. Video needs Content Understanding, and its calls are billed by Azure.
- The file or URL is one you trust. MarkItDown reads files and fetches URLs with your own access rights.

## Examples

```text
# Convert a Word document to Markdown
/trackbed:docs:to-markdown report.docx

# Convert a spreadsheet and save the result to a file
/trackbed:docs:to-markdown data.xlsx and save it as data.md

# Convert a scanned PDF with Azure Document Intelligence for better layout extraction
/trackbed:docs:to-markdown scan.pdf using Azure Document Intelligence
```

## What you get

- The document as Markdown, with its headings, tables, lists, and links kept. It is printed as command output, or saved to the output file you name.
- A question before an existing output file is replaced, or a new file name instead.
- Azure extraction only when you ask for it. Setting an endpoint variable does not turn it on.
- A slower first run while `uvx` caches MarkItDown's dependencies.
