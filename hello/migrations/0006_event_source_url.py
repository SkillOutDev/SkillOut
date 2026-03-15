from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hello', '0005_merge_20260315_1843'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='source_url',
            field=models.URLField(blank=True, null=True),
        ),
    ]
