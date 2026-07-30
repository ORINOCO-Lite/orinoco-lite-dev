# CON website deployment

This repository coordinates the GitHub Actions deployment of the Center for Open Neuroscience website.

The public site is a deterministic static projection. Website content remains in files, edits are proposed as GitHub pull requests, and the action builds and publishes the result without a public metadata backend.

```mermaid
flowchart LR
    E[GitHub-authenticated edit] --> PR[Pull request]
    PR --> C[Review and merge]
    C --> F[Website content files]
    F --> A[GitHub Action]
    A --> O[Orinoco schemas, query, render, and assets]
    O --> S[Static website deployment]
    A -. optional local validation .-> V[Dump-things tools]
    V -. not a public backend .-> A
```

See [the plan](docs/plan.md) for the current architecture and next steps.
