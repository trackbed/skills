# code:harden-security

Use it while you write or change code that handles untrusted input, authentication or sessions, dependencies and lockfiles, personal data, or third-party integrations. The agent then applies secure defaults as it writes the code for your task, and asks before risky changes such as a new authentication flow or a CORS change. It writes no report, and it notes insecure code outside your task instead of fixing it. To audit the security of an existing repository, use `trackbed:code:audit-security`; for a dependency audit, use `trackbed:deps:audit`.

## Examples

```text
# Apply the security rules to the work already under way in this conversation
/trackbed:code:harden-security

# Start a task with the rules applied from the first line of code
/trackbed:code:harden-security add an endpoint that accepts profile picture uploads
```

## What you get

- The code for your task, written with the rules applied: input validated once where it enters the system, parameterized queries, hashed passwords, explicit cookie attributes, rate limits on authentication endpoints, and no secrets or personal data in logs or in the repository.
- A `SIMPLICITY CHECK` line for each piece of work, naming the smallest safeguard that covers the threat.
- An `ASK FIRST` line with a plan, and a pause for your answer, before changes such as a new authentication flow, a CORS or CSP change, a session cookie change, a file upload endpoint, a rate-limit change, or a new third-party integration.
- An `UNVERIFIED` line for each safety assumption it could not confirm, and a `NOTICED BUT NOT TOUCHING` line for insecure code nearby that it left alone.
- For a dependency change, package install scripts stay blocked by default, and the manifest and lockfile diff is reviewed and the dependencies scanned before the change is accepted.

Before the work is called done, the agent checks it against the skill's security checklist and, in Claude Code, runs the `trackbed:security-reviewer` agent on the diff.
