__author__ = 'brianharnett'

from plexapi.myplex import MyPlexUser
user = MyPlexUser.signin('bharnett1825@gmail.com', 'plexytime')
plex = user.getResource('184.75.223.203',23448).connect()

