def apply_ordering(queryset, raw, mapping, default):
    """
    Order by an allowlisted field. ``mapping`` maps client names to model fields;
    unknown fields fall back to ``default`` instead of raising FieldError (HTTP 500).
    """
    if not raw:
        return queryset.order_by(*(default if isinstance(default, (list, tuple)) else [default]))
    desc = raw.startswith("-")
    field = mapping.get(raw.lstrip("-"))
    if not field:
        return queryset.order_by(*(default if isinstance(default, (list, tuple)) else [default]))
    return queryset.order_by(f"-{field}" if desc else field)
