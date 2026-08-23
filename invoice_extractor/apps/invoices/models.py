from django.db import models

class Upload(models.Model):
    file_name = models.CharField(max_length=255)  
    uploaded_file = models.FileField(upload_to='uploads/', null=True, blank=True) 
    json_data = models.JSONField(null=True, blank=True) 
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"File: {self.file_name} (Uploaded on {self.uploaded_at})"
