import urllib
import cherrypy
from sqlalchemy import Column, String, Integer, ForeignKey, Date, Boolean, DateTime, create_engine
from sqlalchemy.orm import relationship, backref, sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from cherrypy.process import wspbus, plugins
import os
import re
import datetime


Base = declarative_base()


class Show(Base):
    __tablename__ = 'show'
    show_id = Column(Integer, primary_key=True)
    show_name = Column(String)
    first_aired = Column(Date)
    is_active = Column(Boolean, default=True)
    banner = Column(String)
    show_directory = Column(String)

    def __str__(self):
        return "%s - %s" % (self.show_name, self.show_id)


class Episode(Base):
    __tablename__ = 'episode'
    id = Column(Integer, primary_key=True)
    show_id = Column(Integer, ForeignKey('show.show_id'))
    show = relationship(Show, backref=backref('episodes', cascade='delete', lazy='dynamic'))
    season_number = Column(Integer)
    episode_number = Column(Integer)
    episode_name = Column(String)
    air_date = Column(Date)
    status = Column(String, default='Retrieved') # 'Pending', 'Retrieved'
    attempts = Column(Integer, default=0)
    retrieved_on = Column(Date)

    def __str__(self):
        return "%s s%se%s" % (self.show.show_name, str(self.season_number).zfill(2), str(self.episode_number).zfill(2))

    def get_episode_name(self):
        return self.episode_name.replace('<', '').replace('>', '')


class ScanURL(Base):
    __tablename__ = 'scanurl'
    id = Column(Integer, primary_key=True)
    username = Column(String, default='myusername')
    password = Column(String, default='mypassword')
    login_page = Column(String, default='http://tehparadox.com/forum/')  # 'http://tehparadox.com/forum/'
    url = Column(String, default='myurl')
    media_type = Column(String, default='both')  # can be tv, movies, or both
    priority = Column(Integer, nullable=True)
    link_select = Column(String, default='a')
    max_search_links = Column(Integer, default=300)
    domain = Column(String, default='http://www.domain.com/')

    def __str__(self):
        return self.domain


class Movie(Base):
    __tablename__ = 'movie'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    link_text = Column(String)
    status = Column(String, default='Not Retrieved')

    def get_IMDB_link(self):
        release_date_list = re.findall('[\(]?[0-9]{4}[\)]?', self.name)
        # s = re.sub('[\(][0-9]{4}[\)]', '', self.name)
        s = self.name.replace('(', '|').replace('Part', '|').replace('Season', '|')
        s = s.split('|')[0].strip()
        s = re.split('[\(]?[0-9]{4}[\)]?', s)[0].strip().replace(' ', '+')
        if len(release_date_list) > 0:
            release_date = release_date_list[0].replace('(', '').replace(')', '')
        else:
            release_date = ''
        s = urllib.parse.quote_plus(s)
        return 'http://www.omdbapi.com/?t=%s&y=%s&plot=short&r=json' % (s, release_date)


class MovieURL(Base):
    __tablename__ = 'movieurl'
    id = Column(Integer, primary_key=True)
    movie_id = Column(Integer, ForeignKey('movie.id'))
    movie = relationship(Movie, backref=backref('movieurls', cascade='delete', lazy='dynamic'))
    url = Column(String)


class ActionLog(Base):
    __tablename__ = 'actionlog'
    id = Column(Integer, primary_key=True)
    time_stamp = Column(DateTime)
    message = Column(String)

    def get_display(self):
        return '%s -- %s' % (self.time_stamp, self.message)

    @staticmethod
    def log(msg):
        # clean up the log file to keep it to the last 2000 records
        s = connect()
        l = ActionLog(time_stamp=datetime.datetime.now(), message=msg)
        s.add(l)

        all_logs = s.query(ActionLog).all()
        if len(all_logs) == 3000:
            entries_to_delete = all_logs[:2000]
            for e in entries_to_delete:
                s.delete(e)
        s.commit()

class LinkIndex(Base):
    __tablename__ = "linkindex"
    id = Column(Integer, primary_key=True)
    link_text = Column(String)
    link_url = Column(String)


class Config(Base):
    __tablename__ = 'config'
    id = Column(Integer, primary_key=True)
    crawljob_directory = Column(String, default='')
    tv_parent_directory = Column(String, default='')
    movies_directory = Column(String, default='')
    file_host_domain = Column(String, default='uploaded.net')  # 'uploaded.net'
    hd_format = Column(String, default='720p')  # only 720p or 1080p
    ip = Column(String, default='127.0.0.1')
    port = Column(String, default='8080')
    scan_interval = Column(Integer, default=12)
    refresh_day = Column(String, default='sun')
    refresh_hour = Column(Integer, default=2)
    jdownloader_restart = Column(Boolean, default=False)

    @staticmethod
    def get_hours():
        return list(range(1, 25))

    @staticmethod
    def get_intervals():
        return list(range(2, 13))

    def is_populated(self):
        if not self.crawljob_directory and not self.tv_parent_directory and not self.movies_directory:
            return False
        else:
            return True

    def domain_link_check(self, link):
        domains = self.file_host_domain.split(',')
        file_host_exists = False
        for d in domains:
            if d.strip() in link:
                file_host_exists = True
                break
        return file_host_exists


        # http://docs.sqlalchemy.org/en/rel_0_9/dialects/sqlite.html


def connect():
    data_file = os.path.normpath(os.path.abspath(__file__))
    print(data_file)
    data_dir = os.path.dirname(data_file)
    db_path = data_dir + '/db.sqlite3'
    print('DB Path: %s' % db_path)
    # engine = create_engine('sqlite:///db.sqlite3', connect_args={'check_same_thread':False})
    engine = create_engine('sqlite:///%s' % db_path, echo=True)
    session_factory = sessionmaker()
    session_factory.configure(bind=engine)
    Base.metadata.create_all(engine)
    s = scoped_session(session_factory)
    return s


# http://www.defuze.org/archives/222-integrating-sqlalchemy-into-a-cherrypy-application.html
class SAEnginePlugin(plugins.SimplePlugin):
    def __init__(self, bus):
        plugins.SimplePlugin.__init__(self, bus)
        self.sa_engine = None
        self.bus.subscribe("bind", self.bind)

    def start(self):
        data_file = os.path.normpath(os.path.abspath(__file__))
        print(data_file)
        data_dir = os.path.dirname(data_file)
        db_path = data_dir + '/db.sqlite3'
        print('DB Path: %s' % db_path)
        self.sa_engine = create_engine('sqlite:///%s' % db_path, echo=True)
        Base.metadata.create_all(self.sa_engine)

    def stop(self):
        if self.sa_engine:
            self.sa_engine.dispose()
            self.sa_engine = None

    def bind(self, session):
        session.configure(bind=self.sa_engine)


class SATool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'on_start_resource',
                               self.bind_session,
                               priority=20)
        self.session = scoped_session(sessionmaker(autoflush=True, autocommit=False))

    def _setup(self):
        cherrypy.Tool._setup(self)
        cherrypy.request.hooks.attach('on_end_resource', self.commit_transaction, priority=80)

    def bind_session(self):
        cherrypy.engine.publish('bind', self.session)
        cherrypy.request.db = self.session

    def commit_transaction(self):
        cherrypy.request.db = None
        try:
            self.session.commit()
        except:
            self.session.rollback()
            raise
        finally:
            self.session.remove()
