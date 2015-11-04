__author__ = 'brianharnett1'
import mechanicalsoup
from models import Show, LinkIndex, ScanURL, ActionLog
import models
import LinkRetrieve


def InitialIndex():
    db = models.connect()
    # check if index is empty to make the default index
    indexes = db.query(LinkIndex).all()

    #if len(indexes) == 0:
        #start new indexing thingy
    source = db.query(ScanURL).filter(ScanURL.media_type == "index").first()
    if (source):
        browser = LinkRetrieve.source_login(source)
        if browser is None:
            ActionLog.log('%s could not logon' % source.login_page)
        else:

            # this is the first page, we have to index by 1 for each subsequent page

            i = 1
            is_indexed = False
            duplicates_encountered = 0

            while is_indexed == False:

                link = source.url
                if i > 1:
                    link = '%sindex%s.html' % (source.url, i)

                soup = browser.get(link).soup


                all_rows_soup = soup.select(source.link_select)  #  get all rows $("#threadbits_forum_73 tr").soup
                for row in all_rows_soup:
                    if 'STICKY' in row.text.upper():
                        continue
                    else:
                        row_links = row.find_all('a')
                        index_link = row_links[0]
                        l = LinkIndex()
                        l.link_text = index_link.text
                        l.link_url = index_link.attrs['href']
                        l.id = int(index_link.attrs['id'].split('_')[2])

                        existing_link_index = db.query(LinkIndex).filter(LinkIndex.id == l.id).first()
                        if existing_link_index:
                            duplicates_encountered += 1
                            if duplicates_encountered > 70:  #this should be 2 plus pages
                                is_indexed = True
                                break
                            else:
                                continue
                        else:
                            db.add(l)



                db.commit()  # commit after a page

                if i == 100000:
                    is_indexed = True
                else:
                    print(i)
                    i += 1



InitialIndex()

