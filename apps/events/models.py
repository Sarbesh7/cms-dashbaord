from django.db import models
from django.utils.text import slugify

# Create your models here.
class Event(models.Model):
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
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at= models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    

    def save(self,*args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        super().save(*args,**kwargs)    

    
  
