import os
import os.path
import tvdb_api
from models import Show, Episode, Movie, MovieURL, ActionLog, ScanURL
import models
import json
import cherrypy
import urllib
from urllib import request
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

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def refresh(self):
        status = 'success'
        try:
            data = cherrypy.request.json
            is_show_refresh = data['isshowrefresh']
            is_scan = data['isscan']

            if is_scan:
                #LinkRetrieve.getepisodes()

            if is_show_refresh:
                #Utils.UpdateAll()

        except Exception as ex:
            ActionLog.ActionLog(ex)
            status = 'error'

        return json.dumps(status)


    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def update_show(self):
        status = 'success'
        try:
            data = cherrypy.request.json
            show_id = data['showid']
            action = data['action']

            if action == 'refresh':
                #Utils.AddEpisodes(show_id)

            if action == 'remove':
                db = models.connect()
                s = db.query(Show).filter(Show.show_id == show_id)
                # for e in s.episode_set:
                #    e.delete
                #remove all episodes since there is no cascade
                ActionLog.log('"%s" removed.' % s.show_name)
                s.delete()

        except Exception as ex:
            # logger.exception(ex)
            status = 'error'

        return json.dumps(status)

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def handlemovie(self):
        status = 'success'
        try:
            data = cherrypy.request.json
            movie_id = data['movieid']
            is_ignore = data['isignore']
            is_cleanup = ['iscleanup']
            db = models.connect()

            if is_cleanup:
                for ignored_movie in db.query(Movie).filter(Movie.status == 'Ignored').all():
                    ignored_movie.delete()
                    # logger.info('Movie DB cleanup completed')
            else:
                m = db.query(Movie).filter(Movie.id == movie_id)
                if is_ignore:
                    m.status = 'Ignored'
                else:
                    jdownloader_string = ''
                    for l in m.movieurls.all():
                        jdownloader_string += l.url + ' '
                    #LinkRetrieve.write_crawljob_file(m.name, SETTINGS.movies_directory, jdownloader_string)
                    ActionLog.log('"%s\'s" .crawljob file created.' % m.name)
                    m.status = 'Retrieved'
                m.save()
        except Exception as ex:
            # logger.exception(ex)
            status = 'error'

        return json.dumps(status)

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def movie_details(self):
        status = 'success'
        try:
            data = cherrypy.request.json

            ombdapi_link = data['omdbapiLink']
            parsed = urllib.parse.urlparse(ombdapi_link)
            urllib.parse.urlparse(parsed.query)
            mdb_url_param = '%s_%s' % (urllib.parse.quote_plus(urllib.parse.parse_qs(parsed.query)['t'][0]), urllib.parse.parse_qs(parsed.query)['y'][0])
            mdb_link = 'https://api.themoviedb.org/3/search/movie?query=%s&api_key=79f408a7da4bdb446799cb45bbb43e7b' % mdb_url_param
            mdb_response = urllib.request.urlopen(mdb_link)
            mdb_json = mdb_response.read()
            mdb_json_string = bytes.decode(mdb_json)
            mdb_data = json.loads(mdb_json_string)
            new_img = 'http://image.tmdb.org/t/p/w154' + mdb_data['results'][0]['poster_path']

            ombdapi_resp = urllib.request.urlopen(ombdapi_link)
            ombdapi_json = json.loads(bytes.decode(ombdapi_resp.read()))
            ombdapi_json['Poster'] = new_img

            status = ombdapi_json

        except Exception as ex:
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
