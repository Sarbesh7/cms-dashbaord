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
    registration_link = models.URLField(blank=True, null=True)
    mentors = models.ManyToManyField('Mentor', related_name='events', blank=True)
    status = models.CharField(max_length=20,choices=[
        ('draft','Draft'),
        ('published','Published'),  
        ('completed','Completed')
    ],
    default ='draft'
    )

    def __str__(self):
        return self.title
    

    def save(self,*args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        super().save(*args,**kwargs)    
        
class Mentor(TimeStampModel):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    expertise = models.CharField(max_length=200)
    linkedin_profile = models.URLField(blank=True, null=True)
    photo = models.ImageField(upload_to='mentors_photos/', null=True, blank=True)
    slug = models.SlugField(unique=True, blank=True,)
    

    def __str__(self):
        return self.name  
     
    def save(self,*args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)

        super().save(*args,**kwargs)   
