

def get_global(template, resource_type, key):
    """Return a value from the Globals section of a SAM template.

    :param template: The template object
    :param resource_type: The resource type being referenced from the Globals
        section
    :param key: The key under the resource to return a value from
    """

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
    if s3_object:
        s3_uri = f's3://{bucket_name}/{bucket_dir}/{s3_object}'

    template['Resources'][resource]['Properties'][resource_param] = s3_uri
