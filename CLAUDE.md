# Trackback: standing instructions
- Before starting any milestone, re-read SPEC_ITERATION_2.md, then the Part 1 section of SPEC.md, then STATUS.md.
- Precedence: SPEC_ITERATION_2.md > SPEC.md Part 1 > SPEC.md Part 2 (design appendix). docs/multi_agent_design.md is the research appendix behind iteration 2.
- The spec is final and approved. Do not brainstorm, do not ask clarifying questions, do not wait for plan approval. Decide, log the decision in DECISIONS.md, and keep going.
- If a skill or plugin (for example a brainstorming or plan-approval skill) wants to ask the user questions or wait for approval, skip that step. Test-driven development, systematic debugging and verification-before-completion skills are welcome.
- Commit at least every 45 minutes. Update STATUS.md at every milestone.
- Demo clock is pinned to 2026-07-08T09:00:00-07:00. Final demo must run offline in replay mode.
- Never commit .env. Never call external services from the app except the Anthropic API in record mode.
- Build commands: `make test`, `make generate`, `TRACKBACK_LLM_MODE=record make world`, `make eval`, `make demo`. Python venv is backend/.venv (3.11).
- Git commits and PRs: do not add a `Co-Authored-By` line or any Claude/AI attribution for now. Credit is added at the end.
