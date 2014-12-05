import os
import datetime
import re

import mechanicalsoup
from models import Show, Episode, Movie, MovieURL, ScanURL, Config
import models


class UploadLink(object):
    def __init__(self, link_text, is_part):
        self.link_text = link_text
        self.is_part = is_part


class Searcher(object):
    def __init__(self, episode_id, episode_code, link, directory):
        self.episode_id = episode_id
        self.episode_code = episode_code
        self.link = link
        self.found = False
        self.directory = directory
        self.search_list = []

    def __str__(self):
        return self.episode_code


def get_episodes():
    # get list of all shows to retrieve
    list_of_shows = []
    db = models.connect()
    config = db.query(Config).first()
    for s in db.query(Show).filter(Show.is_active).all():
        start_date = datetime.date.today() + datetime.timedelta(days=-7)
        end_date = datetime.date.today() + datetime.timedelta(days=1)
        episodes = s.episodes.filter(Episode.air_date <= datetime.date.today()).filter(Episode.status == 'Pending').all()
        # episodes = episodes.filter(air_date__range=(start_date, end_date))
        #episodes = episodes.filter(air_date__lte=datetime.date.today())
        #episodes = episodes.filter(status__exact='Pending')

        for e in episodes:
            # remove dates from show names (2014), (2009) for accurate string searches
            edited_show_name = re.sub('[\(][0-9]{4}[\)]', '', s.show_name)
            edited_show_name = edited_show_name.replace('.', ' ').strip() #remove period and replace with ' ' (for awkward & shield)
            edited_show_name = edited_show_name.replace('\'','') #remove apostrophe as they don't use them in the links
            episode_id_string = 's%se%s' % (str(e.season_number).zfill(2), str(e.episode_number).zfill(2))
            search_string = '%s %s' % (
                edited_show_name, episode_id_string)
            search_episode = Searcher(e.id, search_string.lower(), '', s.show_directory)
            search_episode.search_list.append(edited_show_name.strip().lower())
            search_episode.search_list.append(episode_id_string.lower())
            list_of_shows.append(search_episode)


    if len(list_of_shows) > 0:
        all_tv = ', '.join(str(s) for s in list_of_shows)
    else:
        all_tv = 'no shows'
    models.ActionLog.log('Searching for: %s.' % all_tv)
    browser = mechanicalsoup.Browser()
    login_page = browser.get(config.tp_login_page)

    if login_page.status_code == 200:
        login_form = login_page.soup.select('form')[0]
        login_form.select("#navbar_username")[0]['value'] = config.tp_username
        login_form.select("#navbar_password")[0]['value'] = config.tp_password

        response_page = browser.submit(login_form, login_page.url)

        url_to_check = db.query(ScanURL).first()

        soup = browser.get(url_to_check.url).soup
        soup = soup.select('.post a')[:301]

        # get all links
        for link in soup:
            if link.text != '':
                # get movie links
                regex = re.compile(r'[sS]\d\d[eE]\d\d')
                regex_dated = re.compile(r'[0-9]{4}[\s\S][0-1][0-9][\s\S][0-3][0-9]')
                regex_season = re.compile(r'[sS]eason\s\d{1,2}')
                if regex.search(link.text) is None and regex_dated.search(link.text) is None and regex_season.search(
                        link.text) is None and ('1080p' in link.text or '720p' in link.text):
                    #probably movie - no regex and 1080p so add movie db
                    if db.query(Movie).filter(Movie.name == link_text).first() is None:
                        m = Movie(name=link.text, link_text=link.get('href'), status='Not Retrieved')
                        db.add(m)
                        models.ActionLog.log('"%s" added to downloadable movies' % m.name)
                    continue
                else:
                    #search for all shows
                    #for show_searcher in list_of_shows:
                    for show_searcher in [x for x in list_of_shows if not x.found]:
                        #escape if found or show already found
                        link_text = link.text.lower()
                        #checkf separated code, code, and code without periods (replaced by ' ')
                        if show_searcher.episode_code in link_text or \
                                (show_searcher.search_list[0] in link_text and
                                         show_searcher.search_list[1] in link_text):
                            show_searcher.link = link.get('href')
                            show_searcher.found = True
                            models.ActionLog.log('"%s" found!' % show_searcher)

        # open links and get download links for TV
        for show_searcher in list_of_shows:
            if not show_searcher.found:
                models.ActionLog.log("%s not found in soup" % show_searcher.episode_code)
                continue
            tv_response = browser.get(show_searcher.link)
            if tv_response.status_code == 200:
                episode_soup = tv_response.soup
                episode_links = get_download_links(episode_soup, config, config.hd_format)

                write_crawljob_file(show_searcher.episode_code, show_searcher.directory, ' '.join(episode_links), config.hd_format)

                #use episode id to update database
                db_episode = db.query(Episode).filter(Episode.id == show_searcher.episode_id).first() #models.Episode.objects.get(pk=show_searcher.episode_id)
                db_episode.status = "Retrieved"
                db_episode.save()
                # logger.info("%s retrieved" % show_searcher.episode_code)

        #scan movies
        for movie in db.query(Movie).all():
            #only movies without a movie_link set
            if len(movie.movieurls) == 0:
                movie_response = browser.get(movie.link_text)
                if movie_response.status_code == 200:
                    movie_soup = movie_response.soup
                    movie_links = get_download_links(movie_soup, config, '1080p')

                    for m in movie_links:
                        db.add(MovieURL(url=m, movie=movie))
                        #movie.append(MovieURL(url=m))
                    movie.status = "Ready"
                    movie.save()

    db.commit()


def get_download_links(soup, config, hd_format='720p'):
    code_elements = soup.find_all(text=re.compile('Code'))

    return_links = []

    if len(code_elements) > 0:
        link_text = ''
        for c in code_elements[:-1]:
            if 'code:' in c.lower():
                link_text += ('\n' + c.parent.parent.find('pre').text)

        #link_text = code_elements[0].parent.parent.find('pre').text
        all_links = link_text.split('\n')
        uploaded_links = []
        for l in all_links:
            if config.file_host_domain in l and l[-3:].lower() != 'srt':  #ignore .srt files
                ul = UploadLink(l, '.part.rar' in l)
                uploaded_links.append(ul)

        # check to see if if part files or not
        if len(uploaded_links) == 1:
            # only one uploaded link - return it!
            return_links.append(uploaded_links[0].link_text)
        elif len(uploaded_links) > 1:
            # multiple links - check for parts vs single extraction
            single_extraction_links = []
            part_links = []
            #filter(link for link in uploaded_links if '.mkv' in link.link_text)
            for l in uploaded_links:
                single_extraction_links.append(l) if '.mkv' in l.link_text else part_links.append(l)

            if len(single_extraction_links) == 1:
                #only one .mkv link - get it done
                return_links.append(single_extraction_links[0].link_text)
            elif len(single_extraction_links) == 2:
                #check for HD format if two links
                if hd_format in single_extraction_links[0].link_text:
                    return_links.append(single_extraction_links[0].link_text)
                else:
                    return_links.append(single_extraction_links[1].link_text)
            else:
                #get all the parts for tv and movies
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
    get_episodes()




