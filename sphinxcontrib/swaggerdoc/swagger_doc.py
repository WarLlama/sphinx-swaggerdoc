# -*- coding: utf-8 -*-
from docutils import nodes
from docutils.parsers.rst import Directive, roles, directives
from sphinxcontrib.httpdomain import HTTPGet
import traceback
import os
from sphinx.errors import SphinxError

from sphinx.locale import _

from six.moves.urllib import parse as urlparse   # Retain Py2 compatibility for urlparse
import requests
import json


class SwaggerDocDirective(Directive):

    required_arguments = 1
    has_content = False
    final_argument_whitespace = True  # Just in case you are storing documents in a path that has whitespace.

    def process_source(self, url):
        """
        Fetch and parse the JSON containing the `Resource Listing`_.
        
        https://github.com/OAI/OpenAPI-Specification/blob/master/versions/1.2.md#51-resource-listing
        
        Args:
            url (str): HTTP(S) URL or relative/absolute path in the sphinx source folder.

        Returns:
              dict: Containing the contents of the resource listing
        """
        parsed_url = urlparse.urlparse(url)
        
        if not parsed_url.scheme:  # Assume file relative to documentation
            env = self.state.document.settings.env
            relfn, absfn = env.relfn2path(url)

            if not os.path.exists(absfn):
                raise self.error("File not found: %s" % absfn)

            env.note_dependency(relfn)

            with open(absfn) as fd:
                content = fd.read()

            return json.loads(content)
        else:
            s = requests.Session()
            r = s.get(url)
            return r.json()

    def _field_list_item(self, label, value):
        """Convenience method to create field list items.
        
        Args:
            label: Label text 
            value: Value text 

        Returns:
            nodes.Field Item that may be appended to a field list
        """
        field = nodes.field()
        field += nodes.field_name(text=label)
        fb = nodes.field_body()
        field += fb
        fb += nodes.paragraph(text=value)
        
        return field

    def operations(self, operations, path):
        """Create nodes for an Operation object which typically represents a single HTTP VERB request to one endpoint.
        
        Args:
              operations (list): List of Operation object as described in 
                https://github.com/OAI/OpenAPI-Specification/blob/master/versions/1.2.md#523-operation-object
              path (str): The resource path given from the API Object
              
        Yields:
              nodes
        """
        for operation in operations:

            if 'method' in operation:
                method = operation['method'].upper()
            elif 'httpMethod' in operation:  # Because my vendor is dumb
                method = operation['httpMethod'].upper()

            yield nodes.subtitle(text='{} {}'.format(method, path))
            if 'summary' in operation:
                yield nodes.paragraph(text=operation['summary'])

    def api_endpoints(self, api_objects):
        """Create nodes for api_objects as a generator.
        
        Args:
              api_objects (list): List of API Objects
        Yields:
              docutils nodes
        """
        for api in api_objects:
            print('Creating nodes for API with path: {}'.format(api['path']))
            yield nodes.title(text=api['path'])
            yield nodes.paragraph(text=api['description'])

            for operation in self.operations(api.get('operations', []), api['path']):
                yield operation

    def create_declaration(self, declaration):
        """Create nodes for an API Declaration. This is the root level dict.
        
        Args:
            declaration (dict): The root level of an API Declaration 

        Returns:
            A section containing the API documentation
        """
        s = nodes.section(ids=[declaration['resourcePath']])
        s += nodes.title(text='API')

        fl = nodes.field_list()
        if 'swaggerVersion' in declaration:
            fl += self._field_list_item('Swagger', declaration['swaggerVersion'])

        if 'apiVersion' in declaration:
            fl += self._field_list_item('API Version', declaration['apiVersion'])

        if 'basePath' in declaration:
            fl += self._field_list_item('Base Path', declaration['basePath'])

        if 'resourcePath' in declaration:
            fl += self._field_list_item('Resource Path', declaration['resourcePath'])

        s += fl

        for element in self.api_endpoints(declaration.get('apis', [])):
            s += element

        return s

    def run(self):
        try:
            source_url = self.arguments[0]
            swaggerdoc = self.process_source(source_url)

            return [self.create_declaration(swaggerdoc)]
        except:
            print('Unable to process URL: %s' % self.arguments[0])
            traceback.print_exc()
            error = nodes.error('')
            para = nodes.paragraph()
            para += nodes.Text('Unable to process URL: ')
            para += nodes.strong('', self.arguments[0])
            para += nodes.Text('. Please check that the URL is a valid Swagger api-docs URL and it is accesible')
            error += para
            return [error]
