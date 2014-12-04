import models
from models import Show, Episode

s = models.connect()

current_show = s.query(Show).join(Episode).filter(Show.show_id == 79313).first()

print(current_show.episodes.ordery_by(Episode.air_date))




