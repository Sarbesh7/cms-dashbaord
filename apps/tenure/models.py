from django.db import models

# Create your models here.
class Tenure(models.Model):
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    slug = models.SlugField(unique=True)
    
    
    def __str__(self):
        return self.name

class Member(models.Model):
    tenure = models.ForeignKey(Tenure, on_delete=models.CASCADE, related_name='members')
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    image = models.ImageField(upload_to='member_images/', null=True, blank=True)
    fb_link = models.URLField(null=True, blank=True)
    linkedin_link = models.URLField(null=True, blank=True)
    github_link = models.URLField(null=True, blank=True)
    
    def __str__(self):
        return self.name
    
