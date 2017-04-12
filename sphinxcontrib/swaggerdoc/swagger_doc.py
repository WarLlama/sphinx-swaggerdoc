# -*- coding: utf-8 -*-
from docutils import nodes

from docutils.parsers.rst import Directive

from sphinx.locale import _

from six.moves.urllib import parse as urlparse   # Retain Py2 compatibility for urlparse
import requests
from requests_file import FileAdapter
import json


class SwaggerDocDirective(Directive):

    # this enables content in the directive
    has_content = True

    def processSwaggerURL(self, url):
        parsed_url = urlparse.urlparse(url)
        if not parsed_url.scheme:  # Assume file relative to documentation
            env = self.state.document.settings.env
            relfn, absfn = env.relfn2path(url)
            env.note_dependency(relfn)

            with open(absfn) as fd:
                content = fd.read()

            return json.loads(content).get('apis', None)
        else:
            s = requests.Session()
            s.mount('file://', FileAdapter())
            r = s.get(url)
            return r.json()

    def create_item(self, key, value):
        para = nodes.paragraph()
        para += nodes.strong('', key)
        para += nodes.Text(value)

        item = nodes.list_item()
        item += para

        return item

    def expand_values(self, list):
        expanded_values = ''
        for value in list:
            expanded_values += value + ' '

        return expanded_values

    def make_operation(self, path, operation):
        swagger_node = nodes.admonition(path)
        swagger_node += nodes.title(path, operation['method'].upper() + ' ' + path)

        content = nodes.paragraph()
        content += nodes.Text(operation['summary'])

        bullet_list = nodes.bullet_list()
        bullet_list += self.create_item('Notes: ', operation.get('notes', ''))
        bullet_list += self.create_item('Consumes: ', self.expand_values(operation.get('consumes', '')))
        bullet_list += self.create_item('Produces: ', self.expand_values(operation.get('produces', '')))
        content += bullet_list

        swagger_node += content

        return [swagger_node]

    def run(self):
        try:
            methods = self.processSwaggerURL(self.content[0])

            entries = []

            for method in methods:
                for operation in method['operations']:
                    entries += self.make_operation(method['path'], operation)

            return entries
        except:
            print('Unable to process URL: %s' % self.content[0])
            error = nodes.error('')
            para = nodes.paragraph()
            para += nodes.Text('Unable to process URL: ')
            para += nodes.strong('', self.content[0])
            para += nodes.Text('. Please check that the URL is a valid Swagger api-docs URL and it is accesible')
            error += para
            return [error]
