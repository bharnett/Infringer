from datetime import datetime
import os
import os.path
import tvdb_api
import LinkRetrieve
import Utils
from models import Show, Episode, Movie, MovieURL, ActionLog, ScanURL, Config
import models
import json
import cherrypy
import urllib
from urllib import request
from mako.template import Template
from mako.lookup import TemplateLookup
from webutils import AjaxResponse

my_lookup = TemplateLookup(directories=['html'])
config = Config()


class Infringer(object):
    @cherrypy.expose
    def index(self):
        if config is None:
            raise cherrypy.HTTPRedirect("/config")
        else:
            s = models.connect()
            index_template = my_lookup.get_template('index.html')
            upcoming_episodes = s.query(Episode).filter(Episode.air_date != None).filter(
                Episode.status == 'Pending').order_by(Episode.air_date)[:25]
            index_shows = s.query(Show).order_by(Show.show_name)
            index_movies = s.query(Movie).filter(Movie.status == 'Ready').all()
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
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def update_episode(self):
        status = 'success'
        try:
            db = models.connect()
            data = cherrypy.request.json
            episode_id = data['episodeid']
            change_to_value = data['changeto']
            e = db.query(Episode).filter(Episode.id == episode_id).first()
            e.status = change_to_value
            db.commit()
        except Exception as ex:
            ActionLog.log(ex)
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
                Utils.add_episodes(show_id)

            if action == 'remove':
                db = models.connect()
                s = db.query(Show).filter(Show.show_id == show_id).first()
                ActionLog.log('"%s" removed.' % s.show_name)
                db.delete(s)
                db.commit()

        except Exception as ex:
            # logger.exception(ex)
            status = 'error'

        return json.dumps(status)

    @cherrypy.expose
    def log(self):
        s = models.connect()
        log_template = my_lookup.get_template('log.html')
        logs = s.query(ActionLog).order_by(ActionLog.time_stamp.desc()).all()
        return log_template.render(log=logs)


    @cherrypy.expose
    def config(self):
        db = models.connect()
        config_template = my_lookup.get_template('config.html')
        c = db.query(Config).first()
        if c is None:
            c = Config()
            db.add(c)
            db.commit()
        return config_template.render(config=c)

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def ajax_config(self):
        ar = AjaxResponse('Configuration updated...')
        try:
            data = cherrypy.request.json
            db = models.connect()
            c = db.query(Config).first()
            c.tp_username = data['tp_username']
            c.tp_password = data['tp_password']
            c.tp_password = data['tp_password']
            c.tp_login_page = data['tp_login_page']
            c.crawljob_directory = data['crawljob_directory']
            c.tv_parent_directory = data['tv_parent_directory']
            c.movies_directory = data['movies_directory']
            c.file_host_domain = data['file_host_domain']
            c.hd_format = data['hd_format']
            c.ip = data['ip']
            c.port = data['port']
            db.commit()
        except Exception as ex:
            ar.status = 'error'
            ar.message = Exception

        return ar.to_JSON()


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
                first_aired_date = datetime.strptime(s['firstaired'], "%Y-%m-%d")
                new_show = Show(show_id=series_id, show_name=s['seriesname'], first_aired=first_aired_date,
                                is_active=s.data['status'] == 'Continuing', banner=s['banner'])

                # create folder based on show name:
                main_directory = os.path.join(config.tv_parent_directory,
                                              new_show.show_name.replace('.', '').strip())
                if not os.path.exists(main_directory):
                    os.makedirs(main_directory)
                new_show.show_directory = main_directory

                db.add(new_show)
                db.commit()
                ActionLog.log('"%s" added.' % new_show.show_name)
                Utils.add_episodes(series_id, t, db)
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
                LinkRetrieve.handle_downloads()

            if is_show_refresh:
                Utils.update_all()

        except Exception as ex:
            ActionLog.ActionLog(ex)
            status = 'error'

        return json.dumps(status)

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def handle_movie(self):
        ar = AjaxResponse('Movie downloading...')
        try:
            data = cherrypy.request.json
            movie_id = data['movieid']
            is_ignore = data['isignore']
            is_cleanup = data['iscleanup']
            db = models.connect()

            if is_cleanup:
                db.query(Movie).filter(Movie.status == 'Ignored').delete()
                db.commit()
                ActionLog.log("DB cleanup completed")
            else:
                m = db.query(Movie).filter(Movie.id == movie_id).first()
                if is_ignore:
                    m.status = 'Ignored'
                else:
                    jdownloader_string = ''
                    for l in m.movieurls.all():
                        jdownloader_string += l.url + ' '
                    LinkRetrieve.write_crawljob_file(m.name, config.movies_directory, jdownloader_string, config.crawljob_directory)
                    ActionLog.log('"%s\'s" .crawljob file created.' % m.name)
                    m.status = 'Retrieved'
                db.commit()
        except Exception as ex:
            ActionLog.log('error - ' + ex)
            ar.status = 'error'
            ar.message = ex

        return ar.to_JSON()


    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def movie_details(self, movie_id):
        status = 'success'
        try:
            # data = cherrypy.request.json
            db = models.connect()
            m = db.query(Movie).filter(Movie.id == movie_id).first()
            omdb_api_link = m.get_IMDB_link()
            parsed = urllib.parse.urlparse(omdb_api_link)
            urllib.parse.urlparse(parsed.query)
            mdb_url_param = '%s_%s' % (urllib.parse.quote_plus(urllib.parse.parse_qs(parsed.query)['t'][0]),
                                       urllib.parse.parse_qs(parsed.query)['y'][0])
            mdb_link = 'https://api.themoviedb.org/3/search/movie?query=%s&api_key=79f408a7da4bdb446799cb45bbb43e7b' % mdb_url_param
            mdb_response = urllib.request.urlopen(mdb_link)
            mdb_json = mdb_response.read()
            mdb_json_string = bytes.decode(mdb_json)
            mdb_data = json.loads(mdb_json_string)
            ombdapi_resp = urllib.request.urlopen(omdb_api_link)
            ombdapi_json = json.loads(bytes.decode(ombdapi_resp.read()))
            try:
                if len(mdb_data) > 0:
                    new_img = 'http://image.tmdb.org/t/p/w154' + mdb_data['results'][0]['poster_path']
            except Exception as ex:
                new_img = 'http://146990c1ab4c59b8bbd0-13f1a0753bafdde5bf7ad71d7d5a2da6.r94.cf1.rackcdn.com/techdiff.jpg'

            ombdapi_json['Poster'] = new_img

            status = ombdapi_json

        except Exception as ex:
            status = json.dumps('error')

        return status


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
    db = models.connect()
    config = db.query(models.Config).first()

    if config is not None:
        # cherrypy.server.socket_host = config.ip
        # cherrypy.server.socket_port = config.port

        cherrypy.config.update({
            'server.socket_host': config.ip,
            'server.socket_port': int(config.port),
        })
    my_infringer = Infringer()
    cherrypy.quickstart(my_infringer, '/', conf)
