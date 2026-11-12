# browse

Use it to look at a running web app through a real browser: open a page, see how it is structured, take a screenshot, and read the console and network activity. When your request also asks for it, the skill clicks, types, and hovers, and reports what changed on the page. It is experimental, writes no file, and changes nothing in your repository. For a structured test pass with a written report, use `trackbed:qa`.

## Before you run it

- A browser MCP server is connected: [Claude in Chrome](../mcp-servers.md#claude-in-chrome), [Chrome DevTools](../mcp-servers.md#chrome-devtools), or [Playwright](../mcp-servers.md#playwright).
- The app is already running. The skill does not start a server.
- You are in a local workspace. A Conductor cloud workspace has no browser.

## Arguments

| Argument | Meaning |
| --- | --- |
| `<url>` | The page to open. It must start with `http://` or `https://`. |
| `auto` | Find a dev server that is already running on your machine and open it. When it finds several, or only servers started from another checkout, the skill asks which one to use. |

## Options

| Option         | Effect                             |
| -------------- | ---------------------------------- |
| `--screenshot` | Take a screenshot of the page.     |
| `--console`    | Read the browser console messages. |
| `--network`    | Read the network requests.         |

Without any option, all three run. Pass one or two to get only those.

## Examples

```text
# Open a local page and capture a screenshot, the console, and the network requests
/trackbed:browse http://localhost:3000

# Find the running dev server and open it
/trackbed:browse auto

# Read the console and the network requests, without a screenshot
/trackbed:browse http://localhost:3000 --console --network
```

## What you get

- A `Browse Results` reply: the browser used, the page title, a summary of the page structure, a description of the screenshot, console messages with errors first, and a network summary that highlights failed requests.
- A list of the interactions it performed and what changed on the page after each one.
- No file. The results stay in the conversation.

For a local address the skill prefers Chrome DevTools or Playwright, which normally use their own browser profile. For other sites it prefers Claude in Chrome, which runs in your own Chrome with your signed-in accounts. It opens a new tab unless you ask it to use one you have open, stops at a login it has no credentials for, and asks before any click that deletes, charges, or sends something.
