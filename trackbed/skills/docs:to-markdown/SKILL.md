---
name: docs:to-markdown
description: Convert documents and files to Markdown using markitdown. Use when converting PDF, Word (.docx), PowerPoint (.pptx), Excel (.xlsx, .xls), Outlook messages (.msg), HTML, CSV, JSON, XML, images (with EXIF/OCR), audio (with transcription), video via Azure Content Understanding, ZIP archives, YouTube URLs, or EPubs to Markdown format for LLM processing or text analysis.
disable-model-invocation: false
user-invocable: true
---

# Markdown Converter

Convert files to Markdown with `markitdown`, run on demand via `uvx` — no manual install of markitdown.

**Requires `uv`** (which provides `uvx`). If you hit `uvx: command not found`, install `uv` (https://docs.astral.sh/uv/getting-started/installation/), or fall back to `pipx run 'markitdown[all]'` or `pip install 'markitdown[all]'` and call `markitdown` directly.

**Always pass the `[all]` extras.** PDF, Word, PowerPoint, Excel, Outlook, audio transcription, YouTube, Azure Document Intelligence, and Azure Content Understanding support ship as optional dependencies; bare `uvx markitdown` omits them and fails on those formats with a missing-dependency error. Use the `uvx --from 'markitdown[all]' markitdown …` form shown below. For selective installs, Outlook is the `[outlook]` extra, Azure Document Intelligence is the `[az-doc-intel]` extra, and Azure Content Understanding is the `[az-content-understanding]` extra.

## Basic Usage

```bash
# Convert to stdout
uvx --from 'markitdown[all]' markitdown input.pdf

# Save to file
uvx --from 'markitdown[all]' markitdown input.pdf -o output.md
uvx --from 'markitdown[all]' markitdown input.docx > output.md

# From stdin (add -x to hint the file type)
cat input.pdf | uvx --from 'markitdown[all]' markitdown -x .pdf > output.md
```

Before passing `-o` (or redirecting to a file), check whether the output path exists; if it does, confirm with the user or choose a new name before writing.

## Supported Formats

- **Documents**: PDF, Word (.docx), PowerPoint (.pptx), Excel (.xlsx, .xls), Outlook messages (.msg)
- **Web/Data**: HTML, CSV, JSON, XML
- **Media**: Images (EXIF + OCR), Audio (EXIF + transcription), Video (via Azure Content Understanding)
- **Other**: ZIP (iterates contents), YouTube URLs, EPub

## Options

```text
-o OUTPUT               # Output file (overwrites without confirmation)
-x EXTENSION            # Hint file extension (for stdin)
-m MIME_TYPE            # Hint MIME type
-c CHARSET              # Hint charset (e.g., UTF-8)
-d, --use-docintel      # Use Azure Document Intelligence (file path only, not stdin)
-e, --endpoint ENDPOINT # Document Intelligence endpoint
                        # (default: $MARKITDOWN_DOCINTEL_ENDPOINT)
--use-cu, --use-content-understanding
                        # Use Azure Content Understanding (file path or stdin)
--cu-endpoint ENDPOINT  # Content Understanding endpoint
                        # (default: $MARKITDOWN_CU_ENDPOINT)
--cu-analyzer ID        # Optional Content Understanding analyzer ID
--cu-file-types TYPES   # Comma-separated CU-routed file types, e.g. pdf,jpeg,mp4
-p, --use-plugins       # Enable 3rd-party plugins
--list-plugins          # Show installed plugins
--keep-data-uris        # Keep data URIs in output
```

## Cloud Extraction

Azure Document Intelligence (`-d`) and Azure Content Understanding (`--use-cu`) are mutually exclusive cloud extraction paths. Use Document Intelligence for improved document layout extraction; use Content Understanding when you need multimodal extraction, custom analyzers, or structured fields in YAML front matter. Content Understanding calls are billable Azure API calls; use `--cu-file-types` to restrict which formats route through CU.

- **Endpoint.** Before asking the user for an endpoint, check whether `MARKITDOWN_DOCINTEL_ENDPOINT` (Document Intelligence) or `MARKITDOWN_CU_ENDPOINT` (Content Understanding) is set, for example with `[ -n "${MARKITDOWN_DOCINTEL_ENDPOINT:-}" ]`. When it is, omit `-e` or `--cu-endpoint`; an explicit flag overrides the variable. Ask only when neither the flag nor the variable supplies one.
- **Opt-in.** The variable only supplies the endpoint. Cloud extraction still runs only when you pass `-d` or `--use-cu`; without the flag, markitdown converts offline.
- **Input.** Content Understanding accepts piped stdin (hint the type with `-x`). Document Intelligence needs a file path and rejects stdin, so write piped content to a file first.

## Plugins

`uvx` runs markitdown in an isolated environment, so plugins installed elsewhere are invisible to it. Add each plugin package with uv's `--with` option; otherwise `--list-plugins` reports none and `-p` enables nothing:

```bash
uvx --from 'markitdown[all]' --with your-plugin-package markitdown --list-plugins
uvx --from 'markitdown[all]' --with your-plugin-package markitdown -p input.pdf
```

The `markitdown-ocr` plugin needs an LLM client, which the command line cannot supply. From the CLI it loads but silently skips OCR and falls back to the built-in converter. Use markitdown's Python API with `llm_client` for plugin OCR, or `-d` / `--use-cu` for cloud OCR.

## Examples

```bash
# Convert Word document
uvx --from 'markitdown[all]' markitdown report.docx -o report.md

# Convert Excel spreadsheet
uvx --from 'markitdown[all]' markitdown data.xlsx > data.md

# Convert PowerPoint presentation
uvx --from 'markitdown[all]' markitdown slides.pptx -o slides.md

# Convert an Outlook message
uvx --from 'markitdown[all]' markitdown message.msg -o message.md

# Use Azure Document Intelligence for better PDF extraction
# (endpoint from MARKITDOWN_DOCINTEL_ENDPOINT; otherwise add -e "https://your-resource.cognitiveservices.azure.com/")
uvx --from 'markitdown[all]' markitdown scan.pdf -d

# Use Azure Content Understanding for multimodal or structured extraction
uvx --from 'markitdown[all]' markitdown report.pdf --use-cu --cu-endpoint "https://your-resource.cognitiveservices.azure.com/"

# Pipe input to Content Understanding (endpoint from MARKITDOWN_CU_ENDPOINT)
cat report.pdf | uvx --from 'markitdown[all]' markitdown --use-cu -x .pdf > report.md

# Use a custom Content Understanding analyzer only for PDFs
uvx --from 'markitdown[all]' markitdown invoice.pdf --use-cu --cu-endpoint "https://your-resource.cognitiveservices.azure.com/" --cu-analyzer "invoice-analyzer" --cu-file-types pdf
```

## Security

markitdown reads files and fetches URLs (YouTube, HTML, remote URIs) with the current process's privileges — like `open()` or `requests.get()`. Don't point it at untrusted files or URLs in shared or hosted contexts without validating them first (restrict file paths, URI schemes, and network destinations). See markitdown's Security Considerations.

## Notes

- Output preserves document structure: headings, tables, lists, links
- `-o` overwrites the target file silently; check whether the output path exists first, and if it does, confirm with the user or choose a new name before passing `-o`
- First run caches dependencies; subsequent runs are faster
- On a missing-dependency error for a format, confirm the `[all]` extras are present (or install just the per-format extra, e.g. `'markitdown[pdf]'`, `'markitdown[outlook]'`, `'markitdown[az-doc-intel]'`, or `'markitdown[az-content-understanding]'`); for complex PDFs with poor extraction, use `-d` with Azure Document Intelligence or `--use-cu` with Azure Content Understanding
- When piping via stdin, prefer `-x` (and optionally `-m`/`-c`) for better detection
