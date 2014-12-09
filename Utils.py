import tvdb_api
import datetime
import os
import LinkRetrieve

import models
from models import Show, Episode


def add_episodes(series_id, t=None, db=None):
    is_single_update = False
    if t is None:
        t = tvdb_api.Tvdb()
        is_single_update = True
    if db is None:
        db = models.connect()
    episodes = t[series_id].search('')
    update_show = db.query(Show).filter(Show.show_id == series_id).first()

    update_show.episodes.delete()
    db.commit()

    models.ActionLog.log('Updating "%s"' % update_show.show_name)
    # update_show.episode_set.clear() #remove all old episodes before doing the update
    for e in episodes:
        if e['firstaired'] is None:
            first_aired = None
        else:
            first_aired = datetime.datetime.strptime(e['firstaired'], '%Y-%m-%d').date()

        if is_single_update:
            if first_aired is not None and first_aired >= datetime.date.today()
                episodes_retrieved = 'Pending'
            else:
                episodes_retrieved = 'Retrieved'
        else:
            if first_aired is not None and first_aired >= datetime.date.today() + datetime.timedelta(-2):
                episode_retrieved = 'Pending'
            elif first_aired is None:
                episode_retrieved = 'Pending'
            else:
                episode_retrieved = 'Retrieved'

        new_episode = Episode(season_number=e['seasonnumber'], episode_number=e['episodenumber'],
                              air_date=first_aired, episode_name=str(e).replace('<', '').replace('>', ''),
                              status=episode_retrieved, show=update_show)

        if new_episode.season_number == 0: #skip series extras
            continue;

        db.add(new_episode)
        #update_show.episodes.append(new_episode)
        # update_show.episodes.append(Episode(season_number=e['seasonnumber'], episode_number=e['episodenumber'],
        # air_date=first_aired, episode_name=e, status=episode_retrieved))

        #update_show.save()
    db.commit()


def update_all():
    t = tvdb_api.Tvdb()
    db = models.connect()
    shows = db.query(Show).all()
    for s in shows:
        add_episodes(s.show_id, t, db)


if __name__ == "__main__":
    update_all()
