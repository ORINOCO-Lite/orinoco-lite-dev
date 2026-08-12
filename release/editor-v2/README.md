# Static editor v2 overlay

The reviewed pool UI and nested SHACL Vue commits remain immutable.
Release assembly copies those sources into a temporary build tree, replaces only the review-bundle module with the versioned file in this directory, runs its test, and builds the generic shell.
This keeps the Milestone 3 v1 implementation as an exact rollback fixture while giving released consumers the flattened, backend-free Orinoco v2 contract.
