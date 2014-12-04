import os, os.path
import random
import string

import cherrypy
from mako.template import Template
from mako.lookup import TemplateLookup

my_lookup = TemplateLookup(directories=['html'])


class SampleApp(object):
    @cherrypy.expose
    def index2(self):
        my_template = my_lookup.get_template('index2.html')
        return my_template.render(my_name='Brian', my_world='planet of cherries')


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
    webapp = SampleApp()
    cherrypy.quickstart(webapp, '/', conf)
