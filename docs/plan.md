# CON website deployment plan

## Goal

Deploy the CON website as a static site from reviewed content files using GitHub Actions and reusable Orinoco infrastructure.

## Decisions

- Content files are the source for the website.
- GitHub pull requests provide authentication, review, and curation.
- The public deployment has no dump-things backend server.
- Orinoco components are reused selectively and tracked only when adopted.

## Initial work

1. Identify the current website content and build entry point.
2. Reuse the smallest useful Orinoco workflow and rendering components.
3. Add pull-request validation for content and generated output.
4. Add a merge-to-static-deployment GitHub Action.
5. Document any deliberate divergence from Orinoco workflows.

## Open questions

- Which website repository and branch are authoritative?
- Which Orinoco components can run directly in GitHub Actions without a service?
- What static hosting target should the action publish to?
