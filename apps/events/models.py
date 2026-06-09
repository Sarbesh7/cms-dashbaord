from django.db import models
from django.utils.text import slugify
from apps.core.models import TimeStampModel

# Create your models here.
class Event(TimeStampModel):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True,blank=True)
    description = models.TextField()
    image = models.FileField(upload_to='events_templates/',null=True,blank=True)
    date = models.DateTimeField()
    status = models.CharField(max_length=20,choices=[
        ('draft','Draft'),
        ('published','Published')
    ],
    default ='draft'
    )

    def __Str__(self):
        return self.title
    

    def save(self,*args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        super().save(*args,**kwargs)    

    
  
