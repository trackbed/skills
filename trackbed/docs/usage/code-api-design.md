# code:api-design

Use this experimental skill when you add an HTTP endpoint, a public module, or an SDK function, or change the shape of an existing response, error, or input. It settles the interface before the handler is written: input and output types, error cases and status codes, naming, pagination, where input is validated, and whether calls are safe to retry. Where your project already has an error shape, a naming style, or a pagination format, it matches that instead of its own defaults, and it writes no report file. For the full rules on validating untrusted input, use `trackbed:code:harden-security`.

## Options

| Option | Effect |
| --- | --- |
| `--design-twice` | Draft at least three different shapes for the same problem, compare them, and recommend one before the design rules are applied. Saying "design it twice" or "show me alternatives" does the same. |

## Examples

```text
# Settle the interface you are working on before writing the handler
/trackbed:code:api-design

# Compare several different shapes before settling on one
/trackbed:code:api-design --design-twice
```

## What you get

- A `SIMPLICITY CHECK` line that names the smallest interface that meets the requirement, then the interface written down in the form your project reads, such as a type, an OpenAPI stub, or a comment block.
- The design covers input and output types, one error shape with its HTTP status mapping, naming, pagination for list endpoints, and, for each operation that changes state, whether repeating the call is safe.
- `NOTICED BUT NOT TOUCHING` notes for adjacent endpoints with an inconsistent shape. They are left as they are.
- With `--design-twice`: a note on how the designs were drafted, the problem framing, each design in full, a comparison, one recommendation (a design, a hybrid, or a redesign), and a walk through the hardest realistic scenario with every assumption marked `confirmed` or `assumed`.
