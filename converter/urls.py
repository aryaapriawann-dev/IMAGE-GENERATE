"""
URL configuration for the converter app.
"""
from django.urls import path
from . import views

app_name = 'converter'

urlpatterns = [
    path('', views.index, name='index'),
    path('convert/', views.convert_image, name='convert'),
    path('download/', views.download_image, name='download'),
]
