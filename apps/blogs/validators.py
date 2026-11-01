import html
import re
from urllib.parse import urlparse
from django.core.exceptions import ValidationError

# Raw HTML the dashboard editor itself produces; everything else is rejected.
ALLOWED_INLINE_TAGS = {'u', 'br'}

FENCED_CODE_RE = re.compile(r'(^|\n)(`{3,}|~{3,})[^\n]*\n.*?(\n\2[ \t]*(?=\n|$)|$)', re.DOTALL)
INLINE_CODE_RE = re.compile(r'(`+)(?:(?!\1).)+?\1', re.DOTALL)
HTML_TAG_RE = re.compile(r'<\s*(/?)\s*([a-zA-Z][a-zA-Z0-9-]*)([^>]*)>')
HTML_COMMENT_RE = re.compile(r'<!--.*?-->', re.DOTALL)
# [label](target) and ![alt](target "title"); also reference definitions "[id]: target"
INLINE_LINK_RE = re.compile(r'(!?)\[(?:[^\]\\]|\\.)*\]\(\s*<?([^)\s>]*)>?(?:\s+["\'(][^)]*)?\)')
REFERENCE_DEF_RE = re.compile(r'^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)', re.MULTILINE)
AUTOLINK_RE = re.compile(r'<([a-zA-Z][a-zA-Z0-9+.-]*:[^>\s]*)>')

SAFE_LINK_SCHEMES = {'http', 'https', 'mailto'}
SAFE_IMAGE_SCHEMES = {'http', 'https'}


def _strip_code(value):
    value = FENCED_CODE_RE.sub('\n', value)
    return INLINE_CODE_RE.sub('', value)


def _scheme(target):
    # Markdown renderers decode entities ("javascript&#58;") and browsers ignore
    # control chars/whitespace inside schemes ("java\tscript:")
    cleaned = re.sub(r'[\x00-\x20]', '', html.unescape(target)).lower()
    match = re.match(r'^([a-z][a-z0-9+.-]*):', cleaned)
    return match.group(1) if match else None


def validate_http_url(value, field_label='Image URL'):
    """Absolute http(s) URL only: rejects data:, javascript:, relative and local file paths."""
    if not value:
        return value
    parsed = urlparse(value.strip())
    if parsed.scheme not in SAFE_IMAGE_SCHEMES or not parsed.netloc:
        raise ValidationError(f'{field_label} must be an absolute http(s) URL.')
    return value


def validate_markdown_content(value):
    """
    Reject unsafe constructs in Markdown article content instead of silently rewriting it.

    - Raw HTML is limited to attribute-free <u> and <br> (what the editor toolbar emits).
    - Link targets must be http(s), mailto, or relative ("/", "#").
    - Image sources must be absolute http(s) URLs (no base64/data: or local files).
    Text inside code spans/blocks is ignored.
    """
    if not value or not value.strip():
        raise ValidationError('Article content cannot be empty.')

    scanned = HTML_COMMENT_RE.sub('', _strip_code(value))
    errors = []

    disallowed = set()
    for _closing, tag, attrs in HTML_TAG_RE.findall(scanned):
        if attrs.startswith((':', '@')):
            # Markdown autolink (<https://...>, <me@example.com>); schemes are checked below
            continue
        tag = tag.lower()
        attrs = attrs.strip().rstrip('/').strip()
        if tag not in ALLOWED_INLINE_TAGS or attrs:
            disallowed.add(tag)
    if disallowed:
        errors.append(
            'Raw HTML is not allowed in article content (found: '
            + ', '.join(f'<{t}>' for t in sorted(disallowed))
            + '). Use the editor formatting tools instead.'
        )

    for bang, target in INLINE_LINK_RE.findall(scanned):
        target = target.strip()
        if bang:
            if _scheme(target) not in SAFE_IMAGE_SCHEMES or not urlparse(target).netloc:
                errors.append(f'Image "{target[:80]}" must use an absolute http(s) URL.')
        elif target and not target.startswith(('/', '#')):
            scheme = _scheme(target)
            if scheme is not None and scheme not in SAFE_LINK_SCHEMES:
                errors.append(f'Link "{target[:80]}" uses a disallowed URL scheme ({scheme}:).')

    for target in REFERENCE_DEF_RE.findall(scanned) + AUTOLINK_RE.findall(scanned):
        scheme = _scheme(target)
        if scheme is not None and scheme not in SAFE_LINK_SCHEMES:
            errors.append(f'Link "{target[:80]}" uses a disallowed URL scheme ({scheme}:).')

    if errors:
        # de-duplicate while preserving order
        raise ValidationError(list(dict.fromkeys(errors)))
    return value
