# -*- coding: utf-8 -*-
# Generated by Django 1.10 on 2016-08-24 16:52
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Aritcle',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=256, verbose_name='标题')),
                ('slug', models.CharField(db_index=True, max_length=256, verbose_name='网址')),
                ('content', models.TextField(blank=True, default='', verbose_name='内容')),
                ('published', models.BooleanField(default=True, verbose_name='正式发布')),
                ('author', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='作者')),
            ],
            options={
                'verbose_name': '教程',
                'verbose_name_plural': '教程',
            },
        ),
        migrations.CreateModel(
            name='Column',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=256, verbose_name='栏目名称')),
                ('slug', models.CharField(db_index=True, max_length=256, verbose_name='栏目网址')),
                ('intro', models.TextField(default='', verbose_name='栏目简介')),
            ],
            options={
                'ordering': ['name'],
                'verbose_name': '栏目',
                'verbose_name_plural': '栏目',
            },
        ),
        migrations.AddField(
            model_name='aritcle',
            name='colum',
            field=models.ManyToManyField(to='news.Column', verbose_name='归属栏目'),
        ),
    ]
