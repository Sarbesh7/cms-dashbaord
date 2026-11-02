"""
Centralized media management.

Every Cloudinary/local media asset is identified by the storage name that Django
stored for it (FileField.name, or the ``public_id`` returned by the blog image
upload endpoint). This module:

* maps a stored name to the module that owns it (by upload folder),
* finds every record that still references it (usage check),
* deletes the underlying file only when the caller may manage the owning
  module AND no record references it any more.

Removing an image from a record never deletes the file; deletion is explicit.
External URLs (no stored name) are never sent to storage for deletion.
"""
import logging
import posixpath

from django.core.files.storage import default_storage
from django.db.models import Q, TextField
from django.db.models.functions import Cast

from apps.core.permissions import user_has_permission

logger = logging.getLogger("media")

# Upload folder -> (owning RBAC module, permission needed to delete its files)
MEDIA_FOLDERS = {
    "blogs/": ("blogs", "blogs.update"),
    "events_templates/": ("events", "events.update"),
    "member_images/": ("members", "members.update"),
    "mentors_photos/": ("mentors", "mentors.update"),
    "notices/": ("notices", "notices.update"),
    "president_signatures/": ("tenures", "tenures.update"),
    "certificate_templates/": ("certificates", "certificates.manage_templates"),
    "profile_pictures/": ("accounts", "accounts.update"),
}
STORAGE_PREFIXES = ("media/",)  # optional prefix some storages add to stored names


class MediaError(Exception):
    def __init__(self, message, status_code=400, references=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.references = references or []


def normalize_public_id(value):
    """Validate a stored media name. Returns it unchanged, or raises MediaError."""
    value = (value or "").strip()
    if not value:
        raise MediaError("A stored media public_id is required.")
    lowered = value.lower()
    if lowered.startswith(("http://", "https://", "//", "data:")):
        raise MediaError("External URLs are not stored media and cannot be deleted from storage.")
    if "\\" in value or value.startswith("/") or "\x00" in value:
        raise MediaError("Invalid media public_id.")
    if any(part in ("..", ".") for part in value.split("/")):
        raise MediaError("Invalid media public_id.")
    if posixpath.normpath(value) != value:
        raise MediaError("Invalid media public_id.")
    return value


def _folder_relative(public_id):
    for prefix in STORAGE_PREFIXES:
        if public_id.startswith(prefix):
            return public_id[len(prefix):]
    return public_id


def owning_module(public_id):
    relative = _folder_relative(public_id)
    for folder, spec in MEDIA_FOLDERS.items():
        if relative.startswith(folder):
            return spec
    return None


def _name_variants(public_id):
    relative = _folder_relative(public_id)
    return {public_id, relative, *(p + relative for p in STORAGE_PREFIXES)}


def _file_field_sources():
    from apps.certificates.models import CertificateTemplate
    from apps.events.models import Event, Mentor
    from apps.notices.models import Notice
    from apps.tenure.models import Member, Tenure
    from apps.users.models import User

    return [
        ("events", Event, "image", lambda o: o.title),
        ("members", Member, "image", lambda o: o.name),
        ("mentors", Mentor, "photo", lambda o: o.name or f"Mentor #{o.pk}"),
        ("notices", Notice, "image", lambda o: o.title),
        ("tenures", Tenure, "signature", lambda o: o.name),
        ("certificates", CertificateTemplate, "template_file", lambda o: o.template_name),
        ("accounts", User, "profile_picture", lambda o: o.username),
    ]


def find_references(public_id=None, url=None, exclude_blog_id=None, limit=20):
    """Records that still reference the asset: [{module, id, label}]."""
    from apps.blogs.models import Blog

    references = []
    names = _name_variants(public_id) if public_id else set()

    blog_q = Q()
    for name in names:
        blog_q |= Q(featured_image_public_id=name) | Q(content_images_text__icontains=name) | Q(content__icontains=name)
    if url:
        blog_q |= Q(featured_image_url=url) | Q(content__icontains=url) | Q(content_images_text__icontains=url)
    if blog_q:
        blogs = Blog.objects.annotate(content_images_text=Cast("content_images", TextField())).filter(blog_q)
        if exclude_blog_id not in (None, ""):
            try:
                blogs = blogs.exclude(id=int(exclude_blog_id))
            except (TypeError, ValueError):
                pass
        references += [{"module": "blogs", "id": b.id, "label": b.title} for b in blogs[:limit]]

    if names:
        for module, model, field, label in _file_field_sources():
            for obj in model.objects.filter(**{f"{field}__in": names})[:limit]:
                references.append({"module": module, "id": obj.pk, "label": label(obj)})
    return references


def visible_references(references, user):
    """Hide record titles from modules the user cannot view (counts stay visible)."""
    visible = []
    for ref in references:
        if user_has_permission(user, f"{ref['module']}.view"):
            visible.append(ref)
        else:
            visible.append({"module": ref["module"], "id": None, "label": "Restricted record"})
    return visible


def delete_asset(user, public_id, exclude_blog_id=None, required_module=None, url=None):
    """
    Delete one stored asset after permission and usage checks.
    Raises MediaError (400 invalid / 403 forbidden / 409 in use).
    """
    public_id = normalize_public_id(public_id)
    owner = owning_module(public_id)
    if owner is None:
        raise MediaError("This file is not managed media and cannot be deleted here.", 400)
    module, permission = owner
    if required_module and module != required_module:
        raise MediaError(f"Only {required_module} media can be deleted from this endpoint.", 403)
    if not (user_has_permission(user, "media.delete") and user_has_permission(user, permission)):
        raise MediaError("You do not have permission to delete this media.", 403)

    references = find_references(public_id=public_id, url=url or None, exclude_blog_id=exclude_blog_id)
    if references:
        raise MediaError(
            "Asset cannot be deleted from media storage because it is referenced by other content.", 409,
            references=visible_references(references, user),
        )

    try:
        if default_storage.exists(public_id):
            default_storage.delete(public_id)
    except Exception as exc:
        logger.warning(f"Storage deletion failed for '{public_id}': {exc.__class__.__name__}")
        raise MediaError("The media storage could not delete this file. Please try again.", 502)
    return module
