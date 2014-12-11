__author__ = 'e440614'
from os.path import normpath, basename
import models
s = models.connect()

for show in s.query(models.Show).all():
    new_value = '/' + basename(normpath(show.show_directory))
    show.show_directory = new_value
    s.commit()

s.remove()

