# Project Maintenance Rules

## README synchronization

- Every code change must review README.md and update affected or newly introduced behavior in the same change/commit. Documentation is part of completion.
- Cover features, layout, architecture, APIs, dependencies, environment variables, database schema/migrations, data flows, providers, calculations, caches, scheduled jobs, build/deployment and verification as applicable.
- Remove obsolete descriptions. Describe actual implementation and limitations; do not claim planned features or checks not performed.
- If documented behavior is unaffected, state that README was reviewed and no update was needed in the completion report. Avoid meaningless edits.
- README is Chinese. Use placeholders instead of credentials, personal holdings, databases, backups or signing material.

## Product conventions

- Async views need Skeleton loading, success, empty and error states; preserve valid data after refresh failure where appropriate.
- Keep OTC official NAV separate from estimates and verify China Standard Time dates. Document fallback limitations.
- Database changes must support SQLite and MySQL. Do not silently discard archives.
- Deploy complete frontend assets, verify script/stylesheet content types and relevant business APIs. HTTP 200 alone is not sufficient verification.
- Preserve user changes and keep secrets and generated artifacts out of commits.
