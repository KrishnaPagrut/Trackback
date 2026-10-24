# Project skills

Vendored agent skills for Trackback. Claude Code picks these up automatically from `.claude/skills/`.

| Skill | Use it for | Source (commit) |
|---|---|---|
| `brag` | `/brag`: turn Trackback into a ~20 s launch video with music and share copy (full Hyperframes workflow, `--full`, `--voice`) | [latent-spaces/brag](https://github.com/latent-spaces/brag) `069432c` |
| `brag-slim` | `/brag-slim`: the lean version; on Opus 5.5 `/brag` switches to it automatically | latent-spaces/brag `069432c` |
| `hyperframes`, `hyperframes-cli`, `hyperframes-registry` | HTML-to-video compositions and rendering; the engine full `/brag` hands off to | [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) `b3f5869` |
| `impeccable` | Frontend design, critique, audit, polish (`/impeccable audit`, `polish`, `animate`, ...) with anti-slop rules | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) `69c34b7` |
| `remotion-best-practices`, `remotion-create` | React-based video with Remotion, if we ever want a programmatic demo video instead of Hyperframes | [remotion-dev/skills](https://github.com/remotion-dev/skills) `6c67adc` |

Already available globally (not vendored here): Anthropic `frontend-design`, `webapp-testing`, `ui-ux-pro-max`, `taste`, `design-system`, `ui-styling`.

Video skills need Node and run `npx hyperframes` / `npx remotion`, which fetch packages. That is dev tooling only; the app itself still makes no external calls.
