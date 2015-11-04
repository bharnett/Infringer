from datetime import datetime
import os
import os.path
import webbrowser
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
from apscheduler.schedulers.background import BackgroundScheduler

template_dir = os.path.dirname(os.path.normpath(os.path.abspath(__file__))) + '/html'
my_lookup = TemplateLookup(directories=[template_dir])
scan_refresh_scheduler = BackgroundScheduler()
# cherrypy.request.db = models.connect()


class Infringer(object):
    @cherrypy.expose
    def index(self):
        config = cherrypy.request.db.query(Config).first()
        if not config.is_populated():
            raise cherrypy.HTTPRedirect("/config")
        else:
            index_template = my_lookup.get_template('index.html')
            upcoming_episodes = cherrypy.request.db.query(Episode).filter(Episode.air_date != None).filter(
                Episode.status == 'Pending').order_by(Episode.air_date)[:25]
            index_shows = cherrypy.request.db.query(Show).order_by(Show.show_name)
            index_movies = cherrypy.request.db.query(Movie).filter(Movie.status == 'Ready').all()
            downloaded_shows = cherrypy.request.db.query(Episode).filter(Episode.retrieved_on != None).order_by(
                Episode.retrieved_on.desc())[:50]
            return index_template.render(shows=index_shows, movies=index_movies, upcoming=upcoming_episodes,
                                         downloaded=downloaded_shows)

    @cherrypy.expose
    def show(self, show_id):
        show_template = my_lookup.get_template('show.html')
        current_show = cherrypy.request.db.query(Show).filter(Show.show_id == show_id).first()
        current_episodes = current_show.episodes.order_by(Episode.season_number.desc()).order_by(
            Episode.episode_number.desc()).all()
        return show_template.render(show=current_show, episodes=current_episodes)

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def update_episode(self):
        status = 'success'
        try:
            data = cherrypy.request.json
            episode_id = data['episodeid']
            change_to_value = data['changeto']
            if (change_to_value == 'search'):
                new_status = LinkRetrieve.show_search(episode_id, cherrypy.request.db)
                status = 'success' if new_status == 'Retrieved' else 'failed'
            else:
                change_to_value = change_to_value.title()
                e = cherrypy.request.db.query(Episode).filter(Episode.id == episode_id).first()
                e.status = change_to_value
                cherrypy.request.db.commit()
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
                s = cherrypy.request.db.query(Show).filter(Show.show_id == show_id).first()
                ActionLog.log('"%s" removed.' % s.show_name)
                cherrypy.request.db.delete(s)
                cherrypy.request.db.commit()

        except Exception as ex:
            # logger.exception(ex)
            status = 'error'

        return json.dumps(status)

    @cherrypy.expose
    def log(self):
        log_template = my_lookup.get_template('log.html')
        logs = cherrypy.request.db.query(ActionLog).order_by(ActionLog.time_stamp.desc()).all()
        return log_template.render(log=logs)


    @cherrypy.expose
    def config(self):
        config_template = my_lookup.get_template('config.html')
        c = cherrypy.request.db.query(Config).first()
        s = cherrypy.request.db.query(ScanURL).all()
        if c is None:
            c = Config()
            cherrypy.request.db.add(c)
            cherrypy.request.db.commit()
        return config_template.render(config=c, scanurls=s)

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def ajax_config(self):
        ar = AjaxResponse('Configuration updated...')

        try:
            is_restart = False
            data = cherrypy.request.json
            c = cherrypy.request.db.query(Config).first()
            c.crawljob_directory = data['crawljob_directory']
            c.tv_parent_directory = data['tv_parent_directory']
            c.movies_directory = data['movies_directory']
            c.file_host_domain = data['file_host_domain']
            c.hd_format = data['hd_format']

            # check for changes that need a reschedule
            if c.scan_interval != int(data['scan_interval']):
                scan_refresh_scheduler.reschedule_job('scan_job', trigger='cron',
                                                      hour='*/' + str(data['scan_interval']))

            if c.refresh_day != data['refresh_day'] or c.refresh_hour != int(data['refresh_hour']):
                scan_refresh_scheduler.reschedule_job('refresh_job', trigger='cron', day_of_week=data['refresh_day'],
                                                      hour=str(data['refresh_hour']))

            c.scan_interval = data['scan_interval']
            c.refresh_day = data['refresh_day']
            c.refresh_hour = data['refresh_hour']

            if data['ip'] != c.ip or data['port'] != c.port:
                is_restart = True

            c.ip = data['ip']
            c.port = data['port']
            cherrypy.request.db.commit()

            if is_restart:
                cherrypy.engine.stop()
                cherrypy.server.httpserver = None
                cherrypy.config.update({
                    'server.socket_host': c.ip,
                    'server.socket_port': int(c.port),
                })
                cherrypy.engine.start()
                ar.status = 'redirect'
                ar.message = 'http://%s:%s/config' % (c.ip, c.port)

        except Exception as ex:
            ar.status = 'error'
            ar.message = str(Exception)

        return ar.to_JSON()


    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def config_dirs(self, crawljob_directory='', tv_parent_directory='', movies_directory=''):
        try:
            if crawljob_directory != '':
                test_string = crawljob_directory
            elif tv_parent_directory != '':
                test_string = tv_parent_directory
            else:
                test_string = movies_directory
            validation_response = os.path.isdir(test_string)
        except Exception as ex:
            validation_response = False

        return validation_response


    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def update_scanurl(self):
        ar = AjaxResponse('Data source updated...')
        try:
            data = cherrypy.request.json
            action = data['action']
            if action == 'add':
                new_scanurl = ScanURL()
                ar.message = 'Data source added...'
                cherrypy.request.db.add(new_scanurl)
            else:
                u = cherrypy.request.db.query(ScanURL).filter(ScanURL.id == data['id']).first()
                if action == 'update':
                    setattr(u, data['propertyName'], data['propertyValue'])
                elif action == 'delete':
                    ar.message = 'Data source deleted...'
                    cherrypy.request.db.delete(u)
            cherrypy.request.db.commit()
        except Exception as ex:
            ar.status = 'error'
            ar.message = str(Exception)

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
            # db = models.connect()
            if cherrypy.request.db.query(Show).filter(Show.show_id == series_id).first() is None:
                # save new show to db
                first_aired_date = datetime.strptime(s['firstaired'], "%Y-%m-%d")
                new_show = Show(show_id=series_id, show_name=s['seriesname'], first_aired=first_aired_date,
                                is_active=s.data['status'] == 'Continuing', banner=s['banner'])

                # create folder based on show name:
                new_show.show_directory = '/' + new_show.show_name.replace('.', '').strip()
                phys_directory = cherrypy.request.db.query(Config).first().tv_parent_directory + new_show.show_directory
                if not os.path.exists(phys_directory):
                    os.makedirs(phys_directory)

                cherrypy.request.db.add(new_show)
                cherrypy.request.db.commit()
                ActionLog.log('"%s" added.' % new_show.show_name)
                Utils.add_episodes(series_id, t, cherrypy.request.db)
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
            config = cherrypy.request.db.query(Config).first()
            if is_cleanup:
                cherrypy.request.db.query(Movie).filter(Movie.status == 'Ignored').delete()
                cherrypy.request.db.commit()
                ActionLog.log("DB cleanup completed")
            else:
                m = cherrypy.request.db.query(Movie).filter(Movie.id == movie_id).first()
                if is_ignore:
                    m.status = 'Ignored'
                else:
                    jdownloader_string = ''
                    for l in m.movieurls.all():
                        jdownloader_string += l.url + ' '
                    LinkRetrieve.write_crawljob_file(m.name, config.movies_directory, jdownloader_string,
                                                     config.crawljob_directory)
                    ActionLog.log('"%s\'s" .crawljob file created.' % m.name)
                    m.status = 'Retrieved'
                cherrypy.request.db.commit()
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
            # db = models.connect()
            m = cherrypy.request.db.query(Movie).filter(Movie.id == movie_id).first()
            omdb_api_link = m.get_IMDB_link()
            parsed = urllib.parse.urlparse(omdb_api_link)
            urllib.parse.urlparse(parsed.query)
            movie_name = urllib.parse.parse_qs(parsed.query)['t'][0].replace('+',
                                                                             ' ')  # get the real movie name to use later
            release_year = urllib.parse.parse_qs(parsed.query)['y'][0]
            mdb_url_param = '%s' % (urllib.parse.quote_plus(movie_name))
            mdb_link = 'https://api.themoviedb.org/3/search/movie?query=%s&year=%s&api_key=79f408a7da4bdb446799cb45bbb43e7b' % (
                mdb_url_param, release_year)
            mdb_response = urllib.request.urlopen(mdb_link)
            mdb_json = mdb_response.read()
            mdb_json_string = bytes.decode(mdb_json)
            mdb_data = json.loads(mdb_json_string)
            ombdapi_resp = urllib.request.urlopen(omdb_api_link)
            ombdapi_json = json.loads(bytes.decode(ombdapi_resp.read()))

            # set default
            new_img = 'http://146990c1ab4c59b8bbd0-13f1a0753bafdde5bf7ad71d7d5a2da6.r94.cf1.rackcdn.com/techdiff.jpg'
            try:
                if len(mdb_data['results']) == 1:
                    new_img = 'http://image.tmdb.org/t/p/w154' + mdb_data['results'][0]['poster_path']

                elif len(mdb_data['results']) > 0:  # find the correct image by name and year
                    for mdb_movie in mdb_data['results']:
                        if mdb_movie['title'] == movie_name and mdb_movie['release_date'][:4] == release_year:
                            new_img = 'http://image.tmdb.org/t/p/w154' + mdb_movie['poster_path']
                            break
            except Exception as ex:
                new_img = 'http://146990c1ab4c59b8bbd0-13f1a0753bafdde5bf7ad71d7d5a2da6.r94.cf1.rackcdn.com/techdiff.jpg'

            ombdapi_json['Poster'] = new_img

            status = ombdapi_json

        except Exception as ex:
            status = json.dumps('error')

        return status


    @cherrypy.expose
    def restart(self):
        restart()

    @cherrypy.expose
    def shutdown(self):
        shutdown_template = my_lookup.get_template('shutdown.html')
        scan_refresh_scheduler.shutdown()
        cherrypy.engine.stop()
        cherrypy.server.httpserver = None
        cherrypy.engine.exit()
        return shutdown_template.render()


def restart():
    scan_refresh_scheduler.shutdown()
    cherrypy.engine.exit()
    startup()


def startup():
    conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.staticdir.root': os.path.abspath(os.getcwd()),
            'tools.db.on': True
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': 'static'
        }
    }

    config_session = models.connect()
    config = config_session.query(models.Config).first()

    if config is None:
        config = models.Config()
        config_session.add(config)
        config_session.commit()

    cherrypy.config.update({
        'server.socket_host': config.ip,
        'server.socket_port': int(config.port),
    })
    # config_session.remove()

    scan_refresh_scheduler.add_job(LinkRetrieve.handle_downloads, 'cron', hour='*/' + str(config.scan_interval),
                                   id='scan_job', misfire_grace_time=60)
    scan_refresh_scheduler.add_job(Utils.update_all, 'cron', day_of_week=config.refresh_day,
                                   hour=str(config.refresh_hour), id='refresh_job', misfire_grace_time=60)
    scan_refresh_scheduler.start()

    models.SAEnginePlugin(cherrypy.engine).subscribe()
    cherrypy.tools.db = models.SATool()
    cherrypy.tree.mount(Infringer(), '/', conf)
    cherrypy.engine.start()
    webbrowser.get().open(
        'http://%s:%s' % (cherrypy.config['server.socket_host'], str(cherrypy.config['server.socket_port'])))
    cherrypy.engine.block()


if __name__ == '__main__':
    startup()


