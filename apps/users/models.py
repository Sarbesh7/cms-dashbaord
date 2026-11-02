
from django.contrib.auth.models import AbstractUser
from django.db import models
# Create your models here.


class User(AbstractUser):
  ROLE_CHOICES = (
    ('superadmin', 'Superadmin'),
    ('admin', 'Admin'),
    ('cms_user', 'Cms User'),
    ('operations', 'Operations'),
    ('papers', 'Papers'),
    ('notice', 'Notice'),
    ('blog', 'Blog'),
  )
  role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='cms_user')
  profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
  


