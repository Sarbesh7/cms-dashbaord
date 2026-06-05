from django.db import models

# Create your models here.
class Event(models.Model):
    title = models.CharField(max_length=200)
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

    def __Str__(self):
        return self.title
    
  
