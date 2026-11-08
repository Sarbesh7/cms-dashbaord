from django.db import models
from apps.core.models import TimeStampModel
from django.utils.text import slugify

# Create your models here.
class PastPaper(TimeStampModel):
    SEMESTER_CHOICES = (
        (1, '1st Semester'), (2, '2nd Semester'), (3, '3rd Semester'), (4, '4th Semester'),
        (5, '5th Semester'), (6, '6th Semester'), (7, '7th Semester'), (8, '8th Semester'),
    )
    SUBJECT_CHOICES = (
        ('CSC114', 'Introduction to Information Technology'), ('CSC115', 'C Programming'), ('CSC116', 'Digital Logic'), ('MTH117', 'Mathematics I'), ('PHY118', 'Physics'), ('CSC165', 'Discrete Structures'), ('CSC166', 'Object Oriented Programming (C++)'), ('CSC167', 'Microprocessor'), ('MTH168', 'Mathematics II'), ('STA169', 'Statistics I'), ('CSC211', 'Data Structures and Algorithms'), ('CSC212', 'Numerical Methods'), ('CSC213', 'Computer Architecture'), ('CSC214', 'Computer Graphics'), ('STA215', 'Statistics II'), ('CSC262', 'Theory of Computation'), ('CSC263', 'Computer Networks'), ('CSC264', 'Operating Systems'), ('CSC265', 'Database Management System'), ('CSC266', 'Artificial Intelligence'), ('CSC325', 'Design and Analysis of Algorithms'), ('CSC326', 'System Analysis and Design'), ('CSC327', 'Cryptography'), ('CSC328', 'Simulation and Modeling'), ('CSC329', 'Web Technology'), ('CSC330', 'Multimedia Computing'), ('CSC331', 'Wireless Networking'), ('CSC332', 'Image Processing'), ('CSC333', 'Knowledge Management'), ('CSC334', 'Society and Ethics in IT'), ('CSC335', 'Microprocessor Based Design'), ('CSC375', 'Software Engineering'), ('CSC376', 'Compiler Design and Construction'), ('CSC377', 'E-Governance'), ('CSC378', 'Net Centric Computing'), ('CSC379', 'Technical Writing'), ('CSC380', 'Applied Logic'), ('CSC381', 'E-commerce'), ('CSC382', 'Automation and Robotics'), ('CSC383', 'Neural Networks'), ('CSC384', 'Computer Hardware Design'), ('CSC385', 'Cognitive Science'), ('CSC419', 'Advanced Java Programming (Old)'), ('CSC420', 'Data Warehousing and Data Mining (Old)'), ('CSC421', 'Principles of Management (Old)'), ('CSC423', 'Information Retrieval (Old)'), ('CSC424', 'Database Administration (Old)'), ('CSC425', 'Advanced Java Programming'), ('CSC426', 'Data Warehousing and Data Mining'), ('MGT427', 'Principles of Management'), ('CSC428', 'Project I'), ('CSC429', 'Elective I'), ('CSC475', 'Advanced Database Management'), ('CSC476', 'Internship'), ('CSC477', 'Advanced Networking with IPv6'), ('CSC478', 'Decision Support Systems / Expert Systems'), ('CSC479', 'Elective II')
    )
    subject_name = models.CharField(max_length=20, null=True, blank=True, choices=SUBJECT_CHOICES)
    semester = models.IntegerField(choices=SEMESTER_CHOICES)
    model_set = models.BooleanField(default=False)
    is_old_course = models.BooleanField(default=False, help_text="Toggled True if this paper belongs to the old curriculum.")
    exam_year = models.IntegerField()
    drive_link = models.URLField(max_length=200, blank=True, null=True)
    slug = models.SlugField(max_length=150, blank=True, db_index=True)

    class Meta:
        ordering = ['-exam_year', '-semester', 'subject_name']
        unique_together = ('subject_name', 'semester', 'exam_year', 'model_set', 'is_old_course')
        indexes = [
            models.Index(fields=['semester', '-exam_year'], name='pastpaper_sem_year_idx'),
        ]
        
    def save(self, *args, **kwargs): 
        set_type = "model-set" if self.model_set else "board-exam"
        old_suffix = "-old" if self.is_old_course else ""
        expected_slug = slugify(f"{self.subject_name}-{self.exam_year}-{set_type}{old_suffix}")

        if not self.slug or (self.subject_name and not self.slug.startswith(slugify(str(self.subject_name)))) or (self.is_old_course and "-old" not in self.slug):
            candidate = expected_slug
            counter = 1
            while PastPaper.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{expected_slug}-{counter}"
                counter += 1
            self.slug = candidate
            
        super(PastPaper, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.subject_name} ({self.exam_year}){' [OLD]' if self.is_old_course else ''}"