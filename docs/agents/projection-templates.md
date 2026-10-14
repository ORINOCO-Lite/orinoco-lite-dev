# Inheriting selected upstream templates

A downstream Jinja template can inherit the package's selected `www-from-model` source.
For example, set `homepage.template` in `projection.yaml` to `site-specific/templates/homepage.md.j2` and put this in that file:

```jinja
{% extends "www-from-model:page_templates/homepage.md.j2" %}
{% block content %}
{{ super() }}

Additional editorial content.
{% endblock %}
```

This preserves upstream frontmatter, objectives, relationships, and `params.graphRootNodePID`.
`super()` preserves the parent's content before the addition.
Override another named upstream block only when replacing that block is intentional.
The existing homepage content block suffices for appending editorial content; inserting content between its sections requires upstream extension points.

Qualified `extends`, `include`, and import references are relative to the selected source root.
Unqualified dependencies inside an upstream template are relative to that template's directory and stay in the selected source.
Local templates retain their existing directory lookup.
Paths must be normalized POSIX paths without `..`; use a qualified path to refer to another upstream directory.
Missing parents and invalid paths fail rendering with the record PID and requested template.

Editable installations use the actual nested working checkout.
Installed distributions use their bundled rendering resources.
Website projection and editor preparation use the same renderer; neither requires copying upstream parents into the downstream.
