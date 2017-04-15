import json
import os
import datetime
import re
import urllib

import mechanicalsoup
# import Indexer
from models import Show, Episode, Movie, MovieURL, ScanURL, Config, ActionLog, LinkIndex
import models
import time
from urllib.parse import urlparse, urljoin


class UploadLink(object):
    def __init__(self, link_text):
        self.link_text = link_text
        part_regex = re.compile('\.part.?.?\.rar')
        self.is_part = part_regex.search(self.link_text) is not None


class Searcher(object):
    def __init__(self, episode_id, episode_code, link, directory, attempts=0):
        self.episode_id = episode_id
        self.episode_code = episode_code
        self.link = link
        self.found = False
        self.directory = directory
        self.retrieved = False
        self.search_list = []
        self.attempts = attempts

    def __str__(self):
        return '%s %s' % (self.search_list[0], self.episode_code)

    @staticmethod
    def populate_searcher(episodes, config):
        search_episodes = []
        for e in episodes:
            search_episodes.append(Searcher.populate_episode(e, config.tv_parent_directory))

        return search_episodes

    @staticmethod
    def populate_episode(episode, parent_dir):
        edit_chars = [('', ''), ('.', ' '), ('.', ''), ('&', 'and')]  # first one handles initial non-char-edited name
        second_chars = [('\'', '')]
        # remove dates from show names (2014), (2009) for accurate string searches
        edited_show_name = re.sub('[\(][0-9]{4}[\)]', '', episode.show.show_name)
        episode_id_string = 's%se%s' % (str(episode.season_number).zfill(2), str(episode.episode_number).zfill(2))
        show_dir = parent_dir + episode.show.show_directory
        if not os.path.exists(show_dir):
            os.makedirs(show_dir)
        search_episode = Searcher(episode.id, episode_id_string, '', show_dir, episode.attempts)

        for char in edit_chars:
            char_edit_name = edited_show_name.replace(char[0], char[1]).strip().lower()
            search_episode.search_list.append(char_edit_name)
            for second in second_chars:
                search_episode.search_list.append(char_edit_name.replace(second[0], second[1]).strip().lower())

        # remove duplicates
        search_episode.search_list = list(set(search_episode.search_list))
        return search_episode

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
    #
    # create index after searched the list posts
    #CreateIndexes(False)
    #SearchDbForShow(pending_episodes)  # search db for indexed options

    # search warez-bb.org and puzo by their search forms lastly
    remaining_shows = [s for s in pending_episodes if not s.retrieved]
    show_search_form(None, remaining_shows, models.connect())


def search_sites(list_of_shows):
    db = models.connect()
    config = db.query(Config).first()
    movie_types = ['movies', 'both']
    tv_types = ['tv', 'both']

    # check for jdownloader restart

    try:

        if len(config.jd_path) > 0:
            start_command = 'open "%s"' % config.jd_path
            # start_command = 'open "/Applications/JDownloader"'
            kill_command = 'killall JavaApplicationStub'
            os.system(kill_command)
            time.sleep(10)
            os.system(start_command)
    except Exception as ex:
        ActionLog.log('%s is not a valid directory for JDownloader in OSX.  JDownloader has not restarted.' % config.jd_path)

    for source in db.query(ScanURL).order_by(ScanURL.priority).all():
        tv_is_completed = Searcher.list_completed(list_of_shows)
        if tv_is_completed and source.media_type == 'tv':  # skip tv types list is completed
            continue
        if source.media_type == 'search':
            continue
        browser = source_login(source)
        if browser is None:
            ActionLog.log('%s could not logon' % source.login_page)
            continue
        else:
            ActionLog.log('Scanning %s for %s' % (source.domain, source.media_type))
            try:
                soup = browser.get(source.url).soup
            except Exception as ex:
                continue
            soup = soup.select(source.link_select)[:source.max_search_links + 1]

            for link in soup:
                if link.text != '':
                    if source.media_type in movie_types:
                        if process_movie_link(db, link):  # get movies links
                            continue
                    if source.media_type in tv_types:  # search for all shows
                        if tv_is_completed:  # takes care of 'both' media type sources
                            continue
                        else:
                            for show_searcher in [x for x in list_of_shows if not x.found and not x.retrieved]:
                                link_text = link.text.lower()
                                if show_searcher.search_me(link_text):
                                    show_searcher.link = urljoin(source.domain, link.get('href'))
                                    show_searcher.found = True
                                    ActionLog.log('"%s" found!' % show_searcher)

            # open links and get download links for TV
            link_browser = mechanicalsoup.Browser()  # for checking links
            for show_searcher in [l for l in list_of_shows if not l.retrieved]:
                if not show_searcher.found:
                    ActionLog.log("%s not found in soup" % str(show_searcher))
                    db_episode = db.query(Episode).filter(
                        Episode.id == show_searcher.episode_id).first()
                    db_episode.attempts += 1
                    db.commit()
                    continue
                tv_response = browser.get(show_searcher.link)
                if tv_response.status_code == 200:
                    episode_soup = tv_response.soup
                    episode_links = get_download_links(episode_soup, config, source.domain, config.hd_format)

                    links_valid = True
                    for file_share_link in episode_links:
                        try:
                            if link_browser.get(file_share_link).status_code != 200:
                                links_valid = False
                                show_searcher.found = False
                                show_searcher.retrieved = False
                                ActionLog.log('Just kidding, "%s" had a bad link or links :(' % show_searcher)

                                break
                        except Exception as ex:
                                links_valid = False
                                show_searcher.found = False
                                show_searcher.retrieved = False
                                ActionLog.log('Just kidding, "%s" had a bad link or links :(' % show_searcher)

                                break

                    if links_valid:
                        process_tv_link(db, config, show_searcher, episode_links)

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
                                ActionLog.log('"%s" added to downloadable movies' % movie.name)
                            db.commit()
    db.remove()


def source_login(source):
    # source_domain = urlparse(source.login_page).netloc
    browser = mechanicalsoup.Browser()
    try:
        login_page = browser.get(source.login_page)
    except Exception as ex:
        return None

    if login_page.status_code == 200 and len(login_page.soup.select('form')) > 0:

        if 'tehparadox.com' in source.domain:
            login_form = login_page.soup.select('form')[0]
            login_form.select("#navbar_username")[0]['value'] = source.username
            login_form.select("#navbar_password")[0]['value'] = source.password
            response_page = browser.submit(login_form, login_page.url)
            return browser
        elif 'warez-bb.org' in source.domain or 'x264-bb.com' in source.domain:
            login_form = login_page.soup.select('form')[0]
            login_form.findAll("input", {"type": "text"})[0]['value'] = source.username
            login_form.findAll("input", {"type": "password"})[0]['value'] = source.password
            response_page = browser.submit(login_form, login_page.url)
            return browser
        elif 'puzo.org' in source.domain:
            login_form = login_page.soup.select('form')[1]
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
        episodes = s.episodes.filter(Episode.air_date <= datetime.date.today() - datetime.timedelta(days=1)).filter(
            Episode.status == 'Pending').all()

        if len(episodes) > 0:
            new_search_episodes = Searcher.populate_searcher(episodes, config)
            for n in new_search_episodes:
                list_of_shows.append(n)

    if len(list_of_shows) > 0:
        all_tv = ', '.join(str(s) for s in list_of_shows)
    else:
        all_tv = 'no shows'

    ActionLog.log('Searching for: %s.' % all_tv)
    db.commit()

    return list_of_shows


def show_search(episode_id, db):
    config = db.query(Config).first()
    e = db.query(Episode).get(episode_id)
    search_show = Searcher.populate_episode(e, config.tv_parent_directory)
    search_sources = db.query(ScanURL).filter(ScanURL.media_type == 'search').order_by(ScanURL.priority).all()

    for source in search_sources:
        browser = source_login(source)
        if browser is not None:
            all_hits = []
            query = urllib.parse.urlencode({'q': 'site:%s %s' % ('tehparadox.com', str(search_show))})
            url = 'http://ajax.googleapis.com/ajax/services/search/web?v=1.0&%s' % query
            search_response = urllib.request.urlopen(url)
            search_results = search_response.read().decode("utf8")
            results = json.loads(search_results)
            data = results['responseData']
            hits = data['results']
            all_hits.extend(hits)
            # for i in range(1, len(data['cursor']['pages'])):
            # replace_string = 'start=%s' % str(i-1)
            #     new_string = 'start=%s' % data['cursor']['pages'][i]['start']
            #     new_url = data['cursor']['moreResultsUrl'].replace(replace_string, new_string)
            #     resp = urllib.request.urlopen(new_url)
            #     search_results = search_response.read().decode("utf8")
            #     results = json.loads(search_results)
            #     all_hits.append(results['responseData']['results'])

            usable_links = [x for x in hits if search_show.search_me(
                x['titleNoFormatting'].lower())]  # and has_hd_format(x['titleNoFormatting'].lower())]
            preference_links = [p for p in usable_links if config.hd_format in p['url'].lower()]
            if len(preference_links) > 0:
                usable_links = preference_links

            for l in usable_links:
                if search_show.retrieved:
                    break
                else:
                    tv_response = browser.get(l['url'])
                    if tv_response.status_code == 200:
                        episode_soup = tv_response.soup
                        episode_links = get_download_links(episode_soup, config, source.domain, config.hd_format)
                        process_tv_link(db, config, search_show, episode_links)
            if search_show.retrieved:
                break
    return e.status


def show_search_form(episode_id, episode_list=[], db=None):
    if db is None:
        db = models.connect()

    config = db.query(Config).first()

    if not episode_id is None:
        e = db.query(Episode).get(episode_id)
        search_show = Searcher.populate_episode(e, config.tv_parent_directory)
        episode_list.append(search_show)

    if len(episode_list) > 0:
        all_tv = ', '.join(str(s) for s in episode_list)
    else:
        all_tv = 'no shows'
    ActionLog.log('Searching for: %s.' % all_tv)

    search_sources = db.query(ScanURL).filter(ScanURL.media_type == 'search').order_by(ScanURL.priority).all();
    # search_show = search_for_episode
    for source in search_sources:
        browser = source_login(source)
        if browser is not None:
            # soup = browser.get(source.url).soup  # this is the search page
            # put together search form only for warez.bb for now
            if 'warez-bb.org' in source.domain or 'puzo.org' in source.domain:
                search_page = browser.get(source.url)

                for episode in episode_list:
                    ActionLog.log('Searching for %s.' % episode)
                    time.sleep(15)  # wait five seconds between searches for warez-bb.org
                    submit_search(browser, episode, search_page, source, db)

            else:
                ActionLog.log('%s not supported for search yet.' % source.domain)
        else:
            ActionLog.log('%s could not logon' % source.login_page)


def submit_search(browser, search_show, search_page, source, db):
    config = db.query(Config).first()
    for name in search_show.search_list:
        # make search term
        search_text = "%s %s" % (name, search_show.episode_code)

        search_form = search_page.soup.select('form')[0]
        search_form.findAll("input", {"type": "text"})[0]['value'] = search_text
        response_page = browser.submit(search_form, search_page.url)

        response_links = response_page.soup.select(source.link_select)

        #loop through links
        show_links = [x for x in response_links if
                      name in x.text.lower() and search_show.episode_code in x.text.lower() and config.hd_format in x.text.lower()]
        non_hd_show_links = [x for x in response_links if name in x.text.lower() and search_show.episode_code in x.text.lower() and config.hd_format not in x.text.lower()]
        show_links.extend(non_hd_show_links)  # add these to get non-preferential links last


        for l in show_links:
            if (source.domain in l['href']):
                show_page = l['href']
            else:
                show_page = "%s/%s" % (source.domain, l['href'])

            show_page_response = browser.get(show_page)
            search_show.found = True
            download_links = get_download_links(show_page_response.soup, config, source.domain)
            if len(download_links) > 0:
                ActionLog.log('%s found at %s' % (search_show, show_page))
                process_tv_link(db, config, search_show, download_links)
                break  #exit loop as we have the show
            else:
                ActionLog.log('%s had no download links at %s' % (search_show, show_page))
                continue

        #check if show is found to exit higher loop
        if search_show.retrieved:
            break
        else:
            ActionLog.log('"%s" not found using "%s" (%s of %s)' % (search_show, search_text, search_show.search_list.index(name)+1, len(search_show.search_list)))

    return search_show


def process_tv_link(db, config, show_searcher, episode_links):
    write_crawljob_file(str(show_searcher), show_searcher.directory, ' '.join(episode_links),
                        config.crawljob_directory)
    ActionLog.log('"%s\'s" .crawljob file created.' % str(show_searcher))
    show_searcher.retrieved = True
    # use episode id to update database
    db_episode = db.query(Episode).filter(
        Episode.id == show_searcher.episode_id).first()  # models.Episode.objects.get(pk=show_searcher.episode_id)
    db_episode.status = "Retrieved"
    db_episode.retrieved_on = datetime.date.today()
    db.commit()


def process_movie_link(db, link):
    regex = re.compile(r'[sS]\d\d[eE]\d\d')
    regex_dated = re.compile(r'[0-9]{4}[\s\S][0-1][0-9][\s\S][0-3][0-9]')
    regex_season = re.compile(r'[sS]eason\s\d{1,2}')
    if link.text.strip() != '' and regex.search(link.text) is None and regex_dated.search(
            link.text) is None and regex_season.search(
            link.text) is None and ('1080p' in link.text or '720p' in link.text):
        # probably movie - no regex and 1080p or 720p so add movie db
        edited_link_text = re.sub('\[?.*\]', '', link.text).strip()
        if db.query(Movie).filter(Movie.name == edited_link_text).first() is None:
            m = Movie(name=edited_link_text, link_text=link.get('href'), status='Not Retrieved')
            db.add(m)
            db.commit()
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
    elif 'puzo.org' in domain:
        code_elements = soup.select('.prettyprint')
        if len(code_elements) == 0: return []
        for c in code_elements:
            all_links.append(c.text)
    elif 'x264-bb.com' in domain:
        code_elements = soup.select('.codemain pre')
        for c in code_elements:
            all_links.append(c.text)
    else:
        return return_links

    check_links = '\n'.join(all_links).split('\n')

    for l in [x for x in check_links if not x.strip() == '']:
        if config.domain_link_check(l) and l[-3:].lower() != 'srt':  # ignore .srt files
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
            # prob two episode upload, just get both
            for t in single_extraction_links:
                if hd_format.replace('p', '') in t.link_text:
                    return_links.append(t.link_text)
                elif has_hd_format(t.link_text) is False:  # handle shows without HD format in string, just add them
                    return_links.append(t.link_text)
        else:
            # get all the parts for tv and movies
            if len(part_links) == 0:
                for n in single_extraction_links:
                    return_links.append(n.link_text)
            for p in part_links:
                return_links.append(p.link_text)



                # check to see if link is toast

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


def has_hd_format(link_text):
    if '720' in link_text or '1080' in link_text:
        return True
    else:
        return False


def CreateIndexes(is_full_index=False):
    db = models.connect()
    # check if index is empty to make the default index
    indexes = db.query(LinkIndex).all()

    # if len(indexes) == 0:
    #start new indexing thingy
    source = db.query(ScanURL).filter(ScanURL.media_type == "index").first()
    if (source):
        browser = source_login(source)
        if browser is None:
            ActionLog.log('%s could not logon' % source.login_page)
        else:

            # this is the first page, we have to index by 1 for each subsequent page
            i = 1
            is_indexed = False
            duplicates_encountered = 0
            try:
                while is_indexed == False:

                    link = source.url
                    if i > 1:
                        link = '%sindex%s.html' % (source.url, i)

                    if i % 100 == 0:
                        browser = source_login(source)  # reset the browser session every 100 pages

                    soup = browser.get(link).soup

                    all_rows_soup = soup.select(source.link_select)  #  get all rows $("#threadbits_forum_73 tr").soup
                    page_adds = 0
                    for row in all_rows_soup:
                        if 'STICKY' in row.text.upper():  # skip sticky links
                            continue
                        else:
                            row_links = row.find_all('a')
                            links_with_text = [t for t in row_links if t.text != '']
                            index_link = links_with_text[0]
                            l = LinkIndex()
                            l.link_text = index_link.text
                            l.link_url = index_link.attrs['href']
                            l.id = int(index_link.attrs['id'].split('_')[2])

                            if l.link_text == '':
                                continue

                            existing_link_index = db.query(LinkIndex).filter(LinkIndex.id == l.id).first()
                            if existing_link_index:
                                duplicates_encountered += 1
                                if duplicates_encountered > 10 and not is_full_index:  #this is less than one page
                                    is_indexed = True
                                    break
                                else:
                                    continue
                            else:
                                page_adds += 1
                                db.add(l)
                    if page_adds > 0:
                        db.commit()

                    if i == 100000:
                        is_indexed = True
                    else:
                        print(i)
                        i += 1
            except Exception as ex:
                print(ex)


def SearchDbForShow(list_of_shows):
    db = models.connect()
    source = db.query(ScanURL).filter(ScanURL.media_type == "index").first()

    if source:
        browser = source_login(source)
        if browser is None:
            ActionLog.log('%s could not logon' % source.login_page)
        else:
            for show_searcher in [l for l in list_of_shows if not l.retrieved]:
                config = db.query(models.Config).first()
                matching_indexes = []
                for search_text in show_searcher.search_list:  # all potential links to list
                    matching_indexes.extend(
                        db.query(LinkIndex).filter(LinkIndex.link_text.like('%' + search_text + '%')).filter(
                            LinkIndex.link_text.like('%' + show_searcher.episode_code + '%')).all())

                if len(matching_indexes) > 0:
                    for match in matching_indexes:
                        tv_response = browser.get(match.link_url)
                        if tv_response.status_code == 200:
                            episode_soup = tv_response.soup
                            episode_links = get_download_links(episode_soup, config, source.domain, config.hd_format)
                            # check to make sure links are active
                            for l in episode_links:
                                link_response = browser.get(l)
                                if link_response.status_code == 404:
                                    episode_links = None
                                    break

                            if episode_links:
                                process_tv_link(db, config, show_searcher, episode_links)
                                ActionLog.log('"%s\'s" .crawljob file created.' % str(show_searcher))
                                break  # since


if __name__ == "__main__":
    handle_downloads()





