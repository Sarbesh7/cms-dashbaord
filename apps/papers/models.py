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
        ('CSC114', 'Introduction to Information Technology'), ('CSC115', 'C Programming'), ('CSC116', 'Digital Logic'), ('MTH117', 'Mathematics I'), ('PHY118', 'Physics'), ('CSC165', 'Discrete Structures'), ('CSC166', 'Object Oriented Programming (C++)'), ('CSC167', 'Microprocessor'), ('MTH168', 'Mathematics II'), ('STA169', 'Statistics I'), ('CSC211', 'Data Structures and Algorithms'), ('CSC212', 'Numerical Methods'), ('CSC213', 'Computer Architecture'), ('CSC214', 'Computer Graphics'), ('STA215', 'Statistics II'), ('CSC262', 'Theory of Computation'), ('CSC263', 'Computer Networks'), ('CSC264', 'Operating Systems'), ('CSC265', 'Database Management System'), ('CSC266', 'Artificial Intelligence'), ('CSC325', 'Design and Analysis of Algorithms'), ('CSC326', 'System Analysis and Design'), ('CSC327', 'Cryptography'), ('CSC328', 'Simulation and Modeling'), ('CSC329', 'Web Technology'), ('CSC330', 'Multimedia Computing'), ('CSC331', 'Wireless Networking'), ('CSC332', 'Image Processing'), ('CSC333', 'Knowledge Management'), ('CSC334', 'Society and Ethics in IT'), ('CSC335', 'Microprocessor Based Design'), ('CSC375', 'Software Engineering'), ('CSC376', 'Compiler Design and Construction'), ('CSC377', 'E-Governance'), ('CSC378', 'Net Centric Computing'), ('CSC379', 'Technical Writing'), ('CSC425', 'Advanced Java Programming'), ('CSC426', 'Data Warehousing and Data Mining'), ('MGT427', 'Principles of Management'), ('CSC428', 'Project I'), ('CSC429', 'Elective I'), ('CSC475', 'Advanced Database Management'), ('CSC476', 'Internship'), ('CSC477', 'Advanced Networking with IPv6'), ('CSC478', 'Decision Support Systems / Expert Systems'), ('CSC479', 'Elective II')
    )
    subject_name = models.CharField(max_length=10,null=True, choices=SUBJECT_CHOICES)
    semester = models.IntegerField(choices=SEMESTER_CHOICES)
    model_set = models.BooleanField(default=False)
    exam_year = models.IntegerField()
    drive_link = models.URLField(max_length=200 , blank=True, null=True)
    slug = models.SlugField(max_length=150, blank=True, db_index=True)

    class Meta:
        ordering = ['-exam_year', '-semester', 'subject_name']
        unique_together = ('subject_name', 'semester', 'exam_year')
        
    def save(self, *args, **kwargs): 
        if not self.slug:
            
            set_type = "model-set" if self.model_set else "board-exam"
            
           
            slug_text = f"{self.subject_name}-{self.exam_year}-{set_type}"
            self.slug = slugify(slug_text)
            
        super(PastPaper, self).save(*args, **kwargs)

    def __str__(self):
        return self.subject_name