import os
import datetime
import re

import mechanicalsoup
from models import Show, Episode, Movie, MovieURL, ScanURL, Config, ActionLog
import models
from urllib.parse import urlparse, urljoin


class UploadLink(object):
    def __init__(self, link_text):
        self.link_text = link_text
        part_regex = re.compile('\.part.?.?\.rar')
        self.is_part = part_regex.search(self.link_text) is not None


class Searcher(object):
    def __init__(self, episode_id, episode_code, link, directory):
        self.episode_id = episode_id
        self.episode_code = episode_code
        self.link = link
        self.found = False
        self.directory = directory
        self.search_list = []

    def __str__(self):
        return '%s %s' % (self.search_list[0], self.episode_code)

    def search_me(self, link_text):
        is_found = False
        if self.episode_code in link_text:
            for s in self.search_list:
                if s in link_text:
                    is_found = True
                    return is_found
                else:
                    continue
        return is_found

    @staticmethod
    def list_completed(list_of_shows):
        items = [item for item in list_of_shows if item.found is False]
        return len(items) == 0


def handle_downloads():
    pending_episodes = get_episode_list()
    search_sites(pending_episodes)


def search_sites(list_of_shows):
    db = models.connect()
    config = db.query(Config).first()
    movie_types = ['movies', 'both']
    tv_types = ['tv', 'both']

    for source in db.query(ScanURL).order_by(ScanURL.priority).all():
        tv_is_completed = Searcher.list_completed(list_of_shows)
        if tv_is_completed and source.media_type == 'tv':  #skip tv types list is completed
            continue

        browser = source_login(source)
        if browser is None:
            ActionLog.log('%s could not logon' % source.login_page)
        else:

            soup = browser.get(source.url).soup
            soup = soup.select(source.link_select)[:source.max_search_links + 1]

            for link in soup:
                if link.text != '':
                    if source.media_type in movie_types:
                        if process_movie_link(db, link):  # get movies links
                            continue
                    if source.media_type in tv_types:  # search for all shows
                        if tv_is_completed:  #takes care of 'both' media type sources
                            continue
                        else:
                            for show_searcher in [x for x in list_of_shows if not x.found]:
                                link_text = link.text.lower()
                                if show_searcher.search_me(link_text):
                                    show_searcher.link = urljoin(source.domain, link.get('href'))
                                    show_searcher.found = True
                                    models.ActionLog.log('"%s" found!' % show_searcher)

            # open links and get download links for TV
            for show_searcher in list_of_shows:
                if not show_searcher.found:
                    models.ActionLog.log("%s not found in soup" % str(show_searcher))
                    continue
                tv_response = browser.get(show_searcher.link)
                if tv_response.status_code == 200:
                    episode_soup = tv_response.soup
                    episode_links = get_download_links(episode_soup, config, source.domain, config.hd_format)

                    write_crawljob_file(str(show_searcher), show_searcher.directory, ' '.join(episode_links),
                                        config.crawljob_directory)

                    # use episode id to update database
                    db_episode = db.query(Episode).filter(
                        Episode.id == show_searcher.episode_id).first()  # models.Episode.objects.get(pk=show_searcher.episode_id)
                    db_episode.status = "Retrieved"
                    db.commit()
                    # logger.info("%s retrieved" % show_searcher.episode_code)

            if source.media_type in movie_types:  # scan movies
                for movie in db.query(Movie).all():
                    # only movies without a movie_link set
                    if len(movie.movieurls.all()) == 0:
                        movie_link = urljoin(source.domain, movie.link_text)
                        movie_response = browser.get(movie_link)
                        if movie_response.status_code == 200:
                            movie_soup = movie_response.soup
                            movie_links = get_download_links(movie_soup, config, source.domain, '1080p')

                            if len(movie_links) == 0 or movie.name.strip() == '':
                                db.query(Movie).filter(Movie.id == movie.id).delete()
                            else:
                                for m in movie_links:
                                    db.add(MovieURL(url=m, movie=movie))
                                    db.commit()
                                    # movie.append(MovieURL(url=m))
                                movie.status = "Ready"
                            db.commit()


def source_login(source):
    # source_domain = urlparse(source.login_page).netloc
    browser = mechanicalsoup.Browser()
    try:
        login_page = browser.get(source.login_page)
    except Exception as ex:
        return None

    if login_page.status_code == 200:

        if 'tehparadox.com' in source.domain:
            login_form = login_page.soup.select('form')[0]
            login_form.select("#navbar_username")[0]['value'] = source.username
            login_form.select("#navbar_password")[0]['value'] = source.password
            response_page = browser.submit(login_form, login_page.url)
            return browser
        elif 'warez-bb.org' in source.domain:
            login_form = login_page.soup.select('form')[0]
            login_form.findAll("input", {"type": "text"})[0]['value'] = source.username
            login_form.findAll("input", {"type": "password"})[0]['value'] = source.password
            response_page = browser.submit(login_form, login_page.url)
            return browser
        else:
            return None
    else:
        return None


def get_episode_list():
    list_of_shows = []
    db = models.connect()
    config = db.query(Config).first()

    for s in db.query(Show).filter(Show.is_active).all():
        episodes = s.episodes.filter(Episode.air_date <= datetime.date.today()).filter(
            Episode.status == 'Pending').all()

        for e in episodes:
            # remove dates from show names (2014), (2009) for accurate string searches
            edited_show_name = re.sub('[\(][0-9]{4}[\)]', '', s.show_name)
            episode_id_string = 's%se%s' % (str(e.season_number).zfill(2), str(e.episode_number).zfill(2))

            search_episode = Searcher(e.id, episode_id_string, '', s.show_directory)
            search_episode.search_list.append(edited_show_name.lower())  # regular show name
            search_episode.search_list.append(edited_show_name.replace('.', ' ').strip().lower())  # replace . with ' '
            search_episode.search_list.append(edited_show_name.replace('.', '').strip().lower())  # replace . with ''

            list_of_shows.append(search_episode)

    if len(list_of_shows) > 0:
        all_tv = ', '.join(str(s) for s in list_of_shows)
    else:
        all_tv = 'no shows'

    models.ActionLog.log('Searching for: %s.' % all_tv)
    db.commit()

    return list_of_shows


def process_movie_link(db, link):
    regex = re.compile(r'[sS]\d\d[eE]\d\d')
    regex_dated = re.compile(r'[0-9]{4}[\s\S][0-1][0-9][\s\S][0-3][0-9]')
    regex_season = re.compile(r'[sS]eason\s\d{1,2}')
    if regex.search(link.text) is None and regex_dated.search(
            link.text) is None and regex_season.search(
            link.text) is None and ('1080p' in link.text or '720p' in link.text):
        # probably movie - no regex and 1080p or 720p so add movie db
        edited_link_text = re.sub('\[?.*\]','', link.text).strip()
        if db.query(Movie).filter(Movie.name == edited_link_text).first() is None:
            m = Movie(name=edited_link_text, link_text=link.get('href'), status='Not Retrieved')
            db.add(m)
            db.commit()
            models.ActionLog.log('"%s" added to downloadable movies' % m.name)
        return True
    else:
        return False


def get_download_links(soup, config, domain, hd_format='720p'):
    return_links = []
    uploaded_links = []
    all_links = []

    if 'tehparadox.com' in domain:
        code_elements = soup.find_all(text=re.compile('Code'))
        if len(code_elements) == 0: return []
        for c in code_elements[:-1]:
            if 'code:' in c.lower():
                all_links.append(c.parent.parent.find('pre').text)
    elif 'warez-bb.org' in domain:
        code_elements = soup.select('.code span')
        if len(code_elements) == 0: return []
        for c in code_elements:
            all_links.append(c.text)
    else:
        return return_links

    check_links = '\n'.join(all_links).split('\n')

    for l in check_links:
        if config.file_host_domain in l and l[-3:].lower() != 'srt':  # ignore .srt files
            ul = UploadLink(l)
            uploaded_links.append(ul)

    if len(uploaded_links) == 1:
        # only one uploaded link - return it!
        return_links.append(uploaded_links[0].link_text)
    elif len(uploaded_links) > 1:
        # multiple links - check for parts vs single extraction
        single_extraction_links = []
        part_links = []
        # filter(link for link in uploaded_links if '.mkv' in link.link_text)
        for l in uploaded_links:
            single_extraction_links.append(l) if '.mkv' in l.link_text else part_links.append(l)

        if len(single_extraction_links) == 1:
            # only one .mkv link - get it done
            return_links.append(single_extraction_links[0].link_text)
        elif len(single_extraction_links) == 2:
            # check for HD format if two links
            if hd_format in single_extraction_links[0].link_text:
                return_links.append(single_extraction_links[0].link_text)
            else:
                return_links.append(single_extraction_links[1].link_text)
        else:
            # get all the parts for tv and movies
            for p in part_links:
                return_links.append(p.link_text)

    return return_links


def write_crawljob_file(package_name, folder_name, link_text, crawljob_dir):
    crawljob_file = crawljob_dir + '/%s.crawljob' % package_name.replace(' ', '')

    file = open(crawljob_file, 'w')
    file.write('enabled=TRUE\n')
    file.write('autoStart=TRUE\n')
    file.write('extractAfterDownload=TRUE\n')
    file.write('downloadFolder=%s\n' % folder_name)
    file.write('packageName=%s\n' % package_name.replace(' ', ''))
    file.write('text=%s\n' % link_text)
    file.close()


if __name__ == "__main__":
    handle_downloads()




