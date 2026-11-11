---
type: regex
pattern: 'Title:[^\n]*\n+-{3}\n(?:(?!\n-{3}\n)[\s\S])*(?<![A-Za-z])KILLS-15'
match: not_contains
---
