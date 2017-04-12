from .swagger_doc import SwaggerDocDirective
from .swaggerv2_doc import SwaggerV2DocDirective


def setup(app):
    app.add_directive('swaggerdoc', SwaggerDocDirective)
    app.add_directive('swaggerv2doc', SwaggerV2DocDirective)

