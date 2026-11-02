from django.db import models
import uuid
from apps.events.models import Event 
from apps.core.models import TimeStampModel

#certificate ko template haru ko lagi model
class CertificateTemplate(TimeStampModel):
    template_name = models.CharField(max_length=255)
    template_file=models.FileField(upload_to='certificate_templates/', blank=False, null=False)
    
    def __str__(self):
        return self.template_name

class Certificate(TimeStampModel):
    id = models.AutoField(primary_key=True)
    certificate_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    full_name = models.CharField(max_length=255, db_index=True)
    event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True)
    event_title = models.CharField(max_length=255, blank=True, default='')
    is_project_completed = models.BooleanField(default=True)
    issued_at = models.DateTimeField(auto_now_add=True) 

    def save(self, *args, **kwargs):
        if self.event and not self.event_title:
            self.event_title = self.event.title
        super().save(*args, **kwargs)

    def __str__(self):
        title = self.event.title if self.event else (self.event_title or "No Event")
        return f"{self.full_name} - {title}"