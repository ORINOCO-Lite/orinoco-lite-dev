# Inheriting selected upstream templates

A downstream Jinja template can inherit the package's selected `www-from-model` source.
A site can override individual default policies in `site-specific/projection.yaml` without copying the complete policy:

```yaml
version: 2
extends: default
homepage:
  template: site-specific/templates/homepage.md.j2
pages:
  xyzri:XYZProject:
    select: {} # Render all accepted projects.
    template: site-specific/templates/project.md.j2
```

Each specified operation replaces that operation in the default; omitted operations retain their default values.
An empty `select` removes the default filter.
Page names must exist in the default policy.
Full version 2 policies remain supported.

For the homepage example, put this in `site-specific/templates/homepage.md.j2`:

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

For example, a project template can add fields for a site-owned Hugo layout while retaining the upstream project template:

```jinja
{% extends "www-from-model:page_templates/project.md.j2" %}
{% block frontmatter_params %}
{{ super() }}
  parentProjects:
{% for parent in part_of|default([]) %}
  - {{ parent.pid }}
{% endfor %}
{% endblock %}
```

Keep organization-specific relationship rules in the downstream template.
Inspect the selected upstream template's blocks when choosing where to add or replace content.
