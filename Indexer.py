__author__ = 'brianharnett1'
import mechanicalsoup
from models import Show, LinkIndex, ScanURL, ActionLog
import models
import LinkRetrieve
from LinkRetrieve import source_login



def InitialIndex():
    db = models.connect()
    # check if index is empty to make the default index
    indexes = db.query(LinkIndex).all()

    #if len(indexes) == 0:
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

                    if i%100 == 0:
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
                            #     duplicates_encountered += 1
                            #     if duplicates_encountered > 70:  #this should be 2 plus pages
                            #         is_indexed = True
                            #         break
                            #     else:
                            #         continue
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
        browser = LinkRetrieve.source_login(source)
        if browser is None:
            ActionLog.log('%s could not logon' % source.login_page)
        else:
            for show_searcher in [l for l in list_of_shows if not l.retrieved]:
                config = db.query(models.Config).first()
                matching_indexes = []
                for search_text in show_searcher.search_list:  # all potential links to list
                    matching_indexes.extend(db.query(LinkIndex).filter(LinkIndex.link_text.like('%' + search_text + '%')).filter(LinkIndex.link_text.like('%' + show_searcher.episode_code + '%')).all())

                if len(matching_indexes) > 0:
                    for match in matching_indexes:
                        tv_response = browser.get(match.link_url)
                        if tv_response.status_code == 200:
                            episode_soup = tv_response.soup
                            episode_links = LinkRetrieve.get_download_links(episode_soup, config, source.domain, config.hd_format)
                            # check to make sure links are active
                            for l in episode_links:
                                link_response = browser.get(l)
                                if link_response.status_code == 404:
                                    episode_links = None
                                    break

                            if episode_links:
                                LinkRetrieve.process_tv_link(db, config, show_searcher, episode_links)
                                break  # since we got the download, we can break out of the loop


# x = LinkRetrieve.get_episode_list()
# SearchDbForShow(x)

InitialIndex()

