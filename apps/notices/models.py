from django.db import models
from django.utils.text import slugify
from apps.core.models import TimeStampModel

# Create your models here.
class Notice(TimeStampModel):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, null=True)
    description = models.TextField()
    image = models.FileField(upload_to='notices/', null=True, blank=True)

    status = models.CharField(max_length=20,choices=[
        ('draft','Draft'),
        ('published','Published')
    ],default='draft',null=True,blank=True)

    category = models.CharField(max_length=50,choices=[
        ('administrative','Administrative'),
        ('academic','Academic'),
        ('events','Events')
    ],null=True,blank=True)

    def __str__(self):
        return self.title
    


    def save(self,*args,**kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args,**kwargs)    