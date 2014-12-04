import os
import os.path
import tvdb_api
from models import Show, Episode, Movie, MovieURL, ActionLog, ScanURL
import models
import json
import cherrypy
from mako.template import Template
from mako.lookup import TemplateLookup
from staticsettings import SETTINGS

my_lookup = TemplateLookup(directories=['html'])


class Infringer(object):

    @cherrypy.expose
    def index(self):
        s = models.connect()
        index_template = my_lookup.get_template('index.html')
        upcoming_episodes = s.query(Episode).filter(Episode.air_date != None).filter(Episode.status == 'Pending').order_by(Episode.air_date)[:25]
        index_shows = s.query(Show).order_by(Show.show_name)
        index_movies = s.query(Movie).filter(Movie.status == 'Ready')
        return index_template.render(shows=index_shows, movies=index_movies, upcoming=upcoming_episodes)

    @cherrypy.expose
    def show(self, show_id):
        s = models.connect()
        show_template = my_lookup.get_template('show.html')
        current_show = s.query(Show).filter(Show.show_id == show_id).first()
        current_episodes = current_show.episodes.order_by(Episode.season_number.desc()).order_by(
            Episode.episode_number.desc()).all()
        return show_template.render(show=current_show, episodes=current_episodes)

    @cherrypy.expose
    def log(self):
        s = models.connect()
        log_template = my_lookup.get_template('log.html')
        logs = s.query(ActionLog).order_by(ActionLog.time_stamp.desc()).all()
        return log_template.render(log=logs)


    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def search(self, show_search):
        try:
            t = tvdb_api.Tvdb()
            search_results = t.search(show_search)
            ActionLog.log('Search for "%s".' % show_search)
        except Exception as ex:
            search_results = "{error: %s}" % Exception

        return json.dumps(search_results)


    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def add_show(self):
        status = 'success'
        try:
            data = cherrypy.request.json
            series_id = data['seriesid']
            t = tvdb_api.Tvdb()
            s = t[series_id]
            db = models.connect()
            if db.query(Show).filter(Show.show_id == series_id).first() is None:
                # save new show to db
                new_show = Show(show_id=series_id, show_name=s['seriesname'], first_aired=s['firstaired'],
                                is_active=s.data['status'] == 'Continuing', banner=s['banner'])

                # create folder based on show name:
                main_directory = os.path.join(SETTINGS.tv_parent_directory, new_show.show_name.replace('.', ' ').strip())
                if not os.path.exists(main_directory):
                    os.makedirs(main_directory)
                new_show.show_directory = main_directory

                new_show.save()
                ActionLog.log('"%s" added.' % new_show.show_name)
                #Utils.AddEpisodes(seriesid, t)
            else:
                status = 'duplicate'
                # http://stackoverflow.com/questions/7753073/jquery-ajax-post-to-django-view
        except Exception as ex:
            # logger.exception(ex)
            status = 'error'

        return json.dumps(status)

if __name__ == '__main__':
    conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd())
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': './public'
        }
    }
    my_infringer = Infringer()
    cherrypy.quickstart(my_infringer, '/', conf)
