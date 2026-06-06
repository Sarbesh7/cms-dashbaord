from django.db import models
import uuid
from apps.events.models import Event 

#certificate ko template haru ko lagi model
class CertificateTemplate(models.Model):
    template_name = models.CharField(max_length=255)
    template_file=models.FileField(upload_to='certificate_templates/', blank=False, null=False)
    
    def __str__(self):
        return self.template_name

class Certificate(models.Model):
    certificate_id=models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, unique=True)
    full_name=models.CharField(max_length=255)
    event=models.ForeignKey(Event, on_delete=models.CASCADE) #using event model as event reference
    issued_at=models.DateTimeField(auto_now_add=True) 
    