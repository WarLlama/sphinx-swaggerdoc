#1 -*- coding: utf-8 -*-
from docutils import nodes
import traceback

from docutils.parsers.rst import Directive
from past.builtins import basestring

from sphinx.locale import _

from six.moves.urllib import parse as urlparse   # Retain Py2 compatibility for urlparse
import requests
from requests_file import FileAdapter
import json
import yaml


class SwaggerV2DocDirective(Directive):

    DEFAULT_GROUP = ''

    # this enables content in the directive
    has_content = True

    api_desc = []

    def load_swagger(self, content):
	try:
	    return json.loads(content)
	except JSONDecodeError:
	    return yaml.loads(content)

    def processSwaggerURL(self, url):
        parsed_url = urlparse.urlparse(url)
        if not parsed_url.scheme:  # Assume file relative to documentation
            env = self.state.document.settings.env
            relfn, absfn = env.relfn2path(url)
            env.note_dependency(relfn)

            with open(absfn) as fd:
                content = fd.read()
            return load_swagger(content)
        else:
            s = requests.Session()
            s.mount('file://', FileAdapter())
            r = s.get(url)
            return load_swagger(r.text)

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

    def cell(self, contents):
        if isinstance(contents, basestring):
            contents = nodes.paragraph(text=contents)

        return nodes.entry('', contents)

    def row(self, cells):
        return nodes.row('', *[self.cell(c) for c in cells])

    def create_table(self, head, body, colspec=None):
        table = nodes.table()
        tgroup = nodes.tgroup()
        table.append(tgroup)

        # Create a colspec for each column
        if colspec is None:
            colspec = [1 for n in range(len(head))]

        for width in colspec:
            tgroup.append(nodes.colspec(colwidth=width))

        # Create the table headers
        thead = nodes.thead()
        thead.append(self.row(head))
        tgroup.append(thead)

        # Create the table body
        tbody = nodes.tbody()
        tbody.extend([self.row(r) for r in body])
        tgroup.append(tbody)

        return table

    def make_parameters(self, parameters):
        entries = []
        head = ['Name', 'Position', 'Description', 'Type']
        body = []
        for param in parameters:
            row = []
            req = param.get('required', False)
            if req:
                row.append(param.get('name', '')+'*')
            else:
                row.append(param.get('name', ''))
            row.append(param.get('in', ''))
            row.append(param.get('description', ''))
            t = param.get('type')
            if t is not None:
                row.append(t)
            else:
                s = param.get('schema')
                if s is not None:
                    row.append(self.make_schema('', s))
                else:
                    row.append('')

            body.append(row)
        table = self.create_table(head, body)
        paragraph = nodes.paragraph()
        paragraph += nodes.strong('', 'Parameters')
        entries.append(paragraph)
        entries.append(table)
        return entries

    def make_properties(self, properties, required):
        entries = []
        head = ['Name', 'Description', 'Type']
        body = []
        for name, prop in properties.items():
            row = []
            if name in required:
                row.append(name+'*')
            else:
                row.append(name)
            row.append(prop.get('description', ''))
            row.append(self.make_object('', prop))
            body.append(row)
        table = self.create_table(head, body)
        paragraph = nodes.paragraph()
        paragraph += nodes.strong('', 'Fields')
        entries.append(paragraph)
        entries.append(table)
        return entries

    # Helper function - should really only be called from inside make_schema
    def make_object(self, name, schema):
        ref = schema.get('$ref')
        if ref is not None:
            if ref.startswith('#/responses/'):
                nref = ref.replace('#/responses/', '')
            if ref.startswith('#/definitions/'):
                nref = ref.replace('#/definitions/', '')
            if nref is None:
                swagger_node = nodes.Text("THIS_IS_NOT_RIGHT")
            else:
                swagger_node = nodes.paragraph('')
                swagger_node += nodes.reference('', '', nodes.Text(name + nref), postpone=True, internal=True, refid=nref)
        else:
            type = schema.get('type')
            if type in ['boolean', 'string', 'integer']:
                swagger_node = nodes.Text(name + type)
            elif type == 'array':
                items = schema.get('items')
                if items is not None:
                    swagger_node = self.make_schema(name + 'array of ', items)
                else:
                    swagger_node = nodes.Text("array of UNKNOWN type")
            elif type == 'object':
                props = schema.get('properties')
                if props is not None:
                    swagger_node = self.make_properties(schema.get('properties', {}), schema.get('required', []))
                else:
                    props = schema.get('additionalProperties')
                    if props is not None:
                        swagger_node = nodes.Text(name + " map of strings to " + props.get("type", "Unknown"))
                    else:
                        swagger_node = nodes.Text(name + "Raw Octet Stream")
            elif type is None:
                swagger_node = nodes.Text(name + "No Data Returned")
            else:
                swagger_node = nodes.Text(name + "UNKNOWN type (3) - " + str(schema))

        return swagger_node

    def make_schema(self, name, schema):
        ref = schema.get('$ref')
        if ref is not None:
            if ref.startswith('#/responses/'):
                nref = ref.replace('#/responses/', '')
            if ref.startswith('#/definitions/'):
                nref = ref.replace('#/definitions/', '')
            if nref is None:
                core = nodes.Text("THIS_IS_NOT_RIGHT")
            else:
                core = nodes.paragraph('')
                core += nodes.reference('', '', nodes.Text(name + nref), postpone=True, internal=True, refid=nref)
        else:
            core = nodes.paragraph('Fields')
            core += self.make_object(name, schema)

        return core

    def make_method_responses(self, responses):
        entries = []

        head = ['Code', 'Type']
        body = []
        for code, resp in responses.items():
            row = []

            row.append(code)
            row.append(self.make_schema('', resp))

            body.append(row)

        if len(body) == 0:
            return []

        table = self.create_table(head, body)

        paragraph = nodes.paragraph()
        paragraph += nodes.strong('', 'Responses')

        entries.append(paragraph)
        entries.append(table)

        return entries

    def make_response(self, name, obj):
        schema = obj.get('schema')
        desc = obj.get('description')
        if schema is not None:
            if desc is not None:
                schema['description'] = desc
        else:
            schema = {}
            if desc is not None:
               schema['description'] = desc
        obj = schema

        section = self.create_section(name)

        swagger_node = nodes.admonition(name)
        swagger_node += nodes.title(name, name)

        paragraph = nodes.paragraph()
        paragraph += nodes.Text(obj.get('summary', ''))

        bullet_list = nodes.bullet_list()
        method_sections = {'Description': 'description', 'Consumes': 'consumes', 'Produces': 'produces'}
        for title in method_sections:
            value_name = method_sections[title]
            value = obj.get(value_name)
            if value is not None:
                bullet_list += self.create_item(title + ': \n', value)
        paragraph += bullet_list
        swagger_node += paragraph
        
        param = {}
        param['in'] = 'Body'
        param['schema'] = schema
        param['name'] = 'Payload'
        params = [param]
        swagger_node += self.make_parameters(params)

        section += swagger_node
        return section

    def make_definition(self, name, obj):
        section = self.create_section(name)

        swagger_node = nodes.admonition(name)
        swagger_node += nodes.title(name, name)

        paragraph = nodes.paragraph()
        paragraph += nodes.Text(obj.get('summary', ''))

        bullet_list = nodes.bullet_list()
        method_sections = {'Description': 'description', 'Consumes': 'consumes', 'Produces': 'produces'}
        for title in method_sections:
            value_name = method_sections[title]
            value = obj.get(value_name)
            if value is not None:
                bullet_list += self.create_item(title + ': \n', value)
        paragraph += bullet_list
        swagger_node += paragraph

        swagger_node += self.make_schema('', obj)

        section += swagger_node
        return section

    def make_method(self, path, method_type, method):
        swagger_node = nodes.admonition(path)
        swagger_node += nodes.title(path, method_type.upper() + ' ' + path)

        paragraph = nodes.paragraph()
        paragraph += nodes.Text(method.get('summary', ''))

        bullet_list = nodes.bullet_list()

        method_sections = {'Description': 'description', 'Consumes': 'consumes', 'Produces': 'produces'}
        for title in method_sections:
            value_name = method_sections[title]
            value = method.get(value_name)
            if value is not None:
                bullet_list += self.create_item(title + ': \n', value)

        paragraph += bullet_list

        swagger_node += paragraph

        parameters = method.get('parameters')
        if parameters is not None:
            swagger_node += self.make_parameters(parameters)

        responses = method.get('responses')
        if responses is not None:
            swagger_node += self.make_method_responses(responses)

        return [swagger_node]

    def group_tags(self):
        groups = {}

        if 'tags' in self.api_desc:
            for tag in self.api_desc['tags']:
                groups[tag['name']] = []

        if len(groups) == 0:
            groups[SwaggerV2DocDirective.DEFAULT_GROUP] = []

        for path, methods in self.api_desc['paths'].items():
            for method_type, method in methods.items():
                if SwaggerV2DocDirective.DEFAULT_GROUP in groups:
                    groups[SwaggerV2DocDirective.DEFAULT_GROUP].append((path, method_type, method))
                else:
                    for tag in method['tags']:
                        groups[tag].append((path, method_type, method))

        return groups

    def create_section(self, title):
        section = nodes.section(ids=[title])
        section += nodes.title(title, title)
        return section

    def check_tags(self, selected_tags, tags, api_url):
        invalid_tags = list(set(selected_tags) - set(tags))
        if len(invalid_tags) > 0:
            msg = self.reporter.error("Error. Tag '%s' not found in Swagger URL %s." % (invalid_tags[0], api_url))
            return [msg]

    def run(self):
        self.reporter = self.state.document.reporter

        api_url = self.content[0]

        if len(self.content) > 1:
            selected_tags = self.content[1:]
        else:
            selected_tags = []

        try:
            self.api_desc = self.processSwaggerURL(api_url)

            groups = self.group_tags()

            self.check_tags(selected_tags, groups.keys(), api_url)

            entries = []

            method_section = self.create_section('Methods')
            for tag_name, methods in groups.items():
                if tag_name in selected_tags or len(selected_tags) == 0:
                    section = self.create_section(tag_name)

                    for path, method_type, method in methods:
                        if method_type in ['$ref', 'parameters']:
                            continue
                        section += self.make_method(path, method_type, method)

                    method_section.append(section)
            entries.append(method_section)

            responses_section = self.create_section('Responses')
            for resp_name, response in self.api_desc.get('responses').items():
                responses_section.append(self.make_response(resp_name, response))
            entries.append(responses_section)

            defs_section = self.create_section('Definitions')
            for def_name, def_obj in self.api_desc.get('definitions').items():
                defs_section.append(self.make_definition(def_name, def_obj))
            entries.append(defs_section)

            return entries
        except Exception as e:
            error_message = 'Unable to process URL: %s' % api_url
            print(error_message)
            traceback.print_exc()

            error = nodes.error('')
            para_error = nodes.paragraph()
            para_error += nodes.Text(error_message + '. Please check that the URL is a valid Swagger api-docs URL and it is accesible')
            para_error_detailed = nodes.paragraph()
            para_error_detailed = nodes.strong('Processing error. See console output for a more detailed error')
            error += para_error
            error += para_error_detailed
            return [error]
