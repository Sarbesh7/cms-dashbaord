from django.db import models

# Create your models here.
class Notice(models.Model):
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    image = models.ImageField(upload_to='notices/', null=True, blank=True)

    def __str__(self):
        return self.title