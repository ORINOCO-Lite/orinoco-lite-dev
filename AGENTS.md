# Agent instructions

This repository coordinates a static deployment of the Center for Open Neuroscience website.

- Keep website content in the website submodule's existing content directories.
- Prefer GitHub pull requests as the review and edit boundary for metadata.
- Do not introduce a dump-things backend server for the public deployment.
- Reuse Orinoco components where they fit, especially schemas, query/rendering tools, assets, and workflow actions.
- Keep each component independently branchable inside its own submodule.
- A submodule is tracked by this parent only when the deployment uses it. Until then, its directory may remain untracked.
- Keep credentials in GitHub Actions secrets or other external configuration, never in this repository.
- Keep planning notes concise and record meaningful architectural decisions in `docs/plan.md`.
