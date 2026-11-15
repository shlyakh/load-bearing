# Instructions for coding agents other than Claude Code

The project instructions are in `CLAUDE.md`. Read it first and follow it as written:
the phase gate, the hard rules, the environment, the layout and the conventions apply
to every agent, whatever its name. Where it says "Claude", read "the agent".

The skills are shared, not copied:

- `.agents/skills/scan`, `judge` and `run-candidate` are links to `.claude/skills/`.
- `.claude/skills/providers.md` maps the skills' `search`, `fetch` and `research` steps
  to tools. The provider names are `claude` and `youcom`; they name search back ends
  and output folders (`scorecards/claude/`, `evidence/youcom/`), not the agent that is
  running. An agent without Claude's WebSearch and WebFetch uses its own search and
  fetch tools for the `claude` provider and says so in its report.

Do not edit a skill through `.agents/`; change the file under `.claude/skills/`.
