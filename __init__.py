import os.path
import cherrypy


class Root(object):
    @cherrypy.expose
    def index(self):
        return {'msg': 'Hello world!'}
        
if __name__ == '__main__':
    # Register the Mako plugin
    from makoplugin import MakoTemplatePlugin
    MakoTemplatePlugin(cherrypy.engine, base_dir=os.getcwd()).subscribe()

    # Register the Mako tool
    from makotool import MakoTool
    cherrypy.tools.template = MakoTool()

    # We must disable the encode tool because it
    # transforms our dictionary into a list which
    # won't be consumed by the mako tool
    cherrypy.quickstart(Root(), '', {'/': {'tools.template.on': True,
                                           'tools.template.template': 'index.html',
                                           'tools.encode.on': False}})