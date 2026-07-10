
from django.contrib.auth.models import AbstractUser
from django.db import models
# Create your models here.


class User(AbstractUser):
  ROLE_CHOICES=(
    ('admin','Admin'),
    ('cms_user','Cms User')
  )
  role = models.CharField(max_length=20,choices=ROLE_CHOICES,default='cms_user')
  profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
  


