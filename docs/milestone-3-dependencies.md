# Milestone 3 SHACL Vue dependency review

Status: implementation candidate

Nested SHACL Vue commit: `a4d59e38c909da512fe766b297a39e6e56680aac`

Pool UI wrapper commit: `32124ffae5c7121669d45ad195754d5851b8c36a`

## Outcome

The dependency refresh reduces the original audit from 23 package-level findings (8 moderate, 14 high, and 1 critical) to no production findings and four development-only findings in the documentation toolchain.

The deployed SHACL Vue application now has a zero-finding production audit.
The exact package lock, application and library builds, test suite, documentation build, and a jsdom-backed Markdown sanitization regression all pass.

Reviewed updates include Vue 3.5.41, Vite 7.3.6, Vitest 3.2.7, DOMPurify 3.4.13, Markdown-It 14.3.0, Mermaid 11.16.1, Happy DOM 20.11.2, YAML 2.9.0, and Vuetify 3.13.1.

## Stable documentation boundary

The four remaining findings are confined to the development documentation chain:

```text
vitepress-plugin-mermaid 2.0.17
  -> vitepress 1.6.4
    -> vite 5.4.21
      -> esbuild 0.21.5
```

VitePress 1.6.4 is the latest stable VitePress 1 release and declares Vite `^5.4.14`.
The latest Vite 5 release remains affected.
The patched Vite line is outside that supported range, while VitePress 2 is an alpha release that requires Vite 8 and is outside the Mermaid plugin's declared VitePress 1 peer range.
The package audit reports no supported automatic fix.

Milestone 3 therefore does not force an unsupported dependency override or an alpha documentation migration.
Documentation packages are not present in the deployed browser runtime.
Human acceptance of this bounded development-only exception is tracked as M3-Q017 in the decision register.

## Security review boundary

Markdown preview rendering remains behind DOMPurify and now has a direct XSS regression.
The review also identified existing raw HTML rendering sites for deployment- and schema-authored presentation content.
Those sources are trusted, pinned inputs in this backend-free preview; making them remotely writable requires a separate sanitization design and is tracked as M3-Q016.

Record-derived external actions must accept only HTTP or HTTPS destinations and open a new page without granting it control of the editor window.
The static patch-download work applies that narrow hardening without introducing a browser credential or hosted write service.

The final nested commit includes both the dependency refresh and the static patch-download editor.
The wrapper commit pins that exact nested tree and uses a deterministic build timestamp derived from committed history.
