from .swagger_doc import SwaggerDocDirective
from .swaggerv2_doc import SwaggerV2DocDirective


def setup(app):
    """Sphinx Extension setup
    
    Args:
          app (sphinx.application.Sphinx): The sphinx application
    Returns:
          Metadata dictionary
    """
    app.setup_extension('sphinxcontrib.httpdomain')

    app.add_directive('swaggerdoc', SwaggerDocDirective)
    app.add_directive('swaggerv2doc', SwaggerV2DocDirective)

    return {'version': '0.1.4'}
