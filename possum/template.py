from ruamel.yaml import YAML

from possum.exc import SAMTemplateError


def get_global(template, resource_type, key):
    """Legacy -> Moved to SAMTemplate class."""

    template_globals = template.get('Globals')
    if not template_globals:
        return None

    resource = template_globals.get(resource_type)
    if not resource:
        return None

    return resource.get(key)


def update_template_resource(template, resource, bucket_name, bucket_dir,
                             resource_param='CodeUri',
                             s3_object=None, s3_uri=None):
    """Legacy -> Will be moved to the SAMTemplate class."""
    if s3_object:
        s3_uri = f's3://{bucket_name}/{bucket_dir}/{s3_object}'

    template['Resources'][resource]['Properties'][resource_param] = s3_uri


class SAMTemplate:
    def __init__(self, template_path):
        try:
            with open(template_path) as f:
                self.template = YAML().load(f)
        except Exception as error:
            raise SAMTemplateError(f"Encountered {type(error).__name__}")

        self.api_resources = dict()
        self.lambda_resources = dict()

        self.parse_resources()

    def get_global(self, resource_type, key):
        """Return a value from the Globals section of the SAM template.

        :param resource_type: The resource type being referenced
        :param key: The key under the resource type to return a value from
        """
        globals_ = self.template.get('Globals')
        if not globals_:
            return None

        resource = globals_.get(resource_type)
        if not resource:
            return None

        return resource.get(key)

    def parse_resources(self):
        resources = self.template['Resources']
        for k, v in resources.items():
            if v['Type'] == 'AWS::Serverless::Function':
                runtime = v['Properties'].get(
                    'Runtime', self.get_global('Function', 'Runtime'))

                if not runtime.startswith('python'):
                    continue

                self.lambda_resources[k] = v

            elif v['Type'] == 'AWS::Serverless::Api':
                if v['Properties'].get('DefinitionUri') and not \
                        v['Properties']['DefinitionUri'].startswith('s3://'):
                    self.api_resources[k] = v

    def get_lambda_handler(self, lambda_name):
        func = self.lambda_resources.get(lambda_name)
        handler = func['Properties'].get(
            'Handler', self.get_global('Function', 'Handler'))

        if handler:
            return handler.split('.')[0] + '.py'
        else:
            return None
