# -*- coding: utf-8 -*-
import cherrypy
from mako import exceptions
from mako.template import Template

__all__ = ['MakoTool']

class MakoTool(cherrypy.Tool):
    def __init__(self):
        cherrypy.Tool.__init__(self, 'before_finalize',
                               self._render,
                               priority=10)
        
    def _render(self, template=None, debug=False):
        """
        Applied once your page handler has been called. It
        looks up the template from the various template directories
        defined in the mako plugin then renders it with
        whatever dictionary the page handler returned.
        """
        if cherrypy.response.status > 399:
            return

        # retrieve the data returned by the handler
        data = cherrypy.response.body or {}
        template = cherrypy.engine.publish("lookup-template", template).pop()

        if template and isinstance(data, dict):
            # dump the template using the dictionary
            if debug:
                try:
                    cherrypy.response.body = template.render(**data)
                except:
                    cherrypy.response.body = exceptions.html_error_template().render()
            else:
                cherrypy.response.body = template.render(**data)