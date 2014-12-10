import urllib
from sqlalchemy import Column, String, Integer, ForeignKey, Date, Boolean, DateTime, create_engine
from sqlalchemy.orm import relationship, backref, sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
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
    status = Column(String, default='Retrieved')

    def __str__(self):
        return "%s s%se%s" % (self.show.show_name, str(self.season_number).zfill(2), str(self.episode_number).zfill(2))

    def get_episode_name(self):
        return self.episode_name.replace('<','').replace('>','')


class ScanURL(Base):
    __tablename__ = 'scanurl'
    id = Column(Integer, primary_key=True)
    username = Column(String, default='myusername')
    password = Column(String, default='mypassword')
    login_page = Column(String, default='http://tehparadox.com/forum/') #'http://tehparadox.com/forum/'
    url = Column(String, default='myurl')
    media_type = Column(String, default='both') #can be tv, movies, or both
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
        release_date_list = re.findall('[\(]?[0-9]{4}[\)]?',self.name)
        #s = re.sub('[\(][0-9]{4}[\)]', '', self.name)
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
        #clean up the log file to keep it to the last 2000 records
        s = connect()
        l = ActionLog(time_stamp=datetime.datetime.now(), message=msg)
        s.add(l)

        all_logs = s.query(ActionLog).all()
        if len(all_logs) == 3000:
            entries_to_delete = all_logs[:2000]
            for e in entries_to_delete:
                s.delete(e)
        s.commit()


class Config(Base):
    __tablename__ = 'config'
    id = Column(Integer, primary_key=True)
    crawljob_directory = Column(String, default='')
    tv_parent_directory = Column(String, default='')
    movies_directory = Column(String, default='')
    file_host_domain = Column(String, default='uploaded.net') #'uploaded.net'
    hd_format = Column(String, default='720p') # only 720p or 1080p
    ip = Column(String, default='127.0.0.1')
    port = Column(String, default='8080')
    scan_interval = Column(Integer, default=12)
    refresh_day = Column(String, default='sun')
    refresh_hour = Column(Integer, default=2)

    @staticmethod
    def get_hours():
        return list(range(1, 25))

    @staticmethod
    def get_intervals():
        return list(range(2, 13))


    #http://docs.sqlalchemy.org/en/rel_0_9/dialects/sqlite.html
def connect():
    db_path = 'sqlite:///' + os.path.join(os.path.abspath(os.getcwd()), 'db.sqlite3')
    #engine = create_engine('sqlite:///db.sqlite3', connect_args={'check_same_thread':False})
    engine = create_engine(db_path, connect_args={'check_same_thread':False})
    session_factory = sessionmaker()
    session_factory.configure(bind=engine)
    Base.metadata.create_all(engine)
    s = scoped_session(session_factory)
    return s