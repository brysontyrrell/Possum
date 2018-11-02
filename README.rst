Possum
======

*Python AWS SAM* --> *PyAWSSAM* --> *Pawssam* --> **Possum**

Install
-------

Possum can be installed from the Python Package Index:

::

    $ pip install possum

Possum requires **Python 3.6+** and **pipenv** (*pipenv* must be installed
separately and is not installed with Possum).

About
-----

Possum is a packaging tool for serverless Python-based applications
using the AWS Serverless Application Model (AWS SAM).

The ``sam package`` or ``aws cloudformation package`` options have a
limitation when it comes to Python Lambda functions: they have no means
of packaging external dependencies. This means that developers are
always on their own for creating those Lambda artifacts, uploading them
to S3, and deploying.

Possum aims to serve as a replacement to the basic package functions.
The tool is based upon my approach to serverless AWS applications
(opinionated) and may not be a fit for all parties.

Basic Usage
-----------

Run Possum from the repository directory containing the serverless application.
You can view the available options and commands for Possum with the ``-h``
argument:

::

    $ possum -h
    usage: possum [-h] [-v] {package,generate-requirements,build-docker-image} ...

    Possum is a utility to package Python-based serverless applications using
    the Amazon Serverless Application model with per-function dependencies.

    Global Options:
      -h, --help            show this help message and exit
      -v, --version         Display version information.

    Commands:
        package             Package the Serverless application, upload to S3, and
                            generate a deployment template file.
        generate-requirements
                            Generate 'requirements.txt' files for each Lambda
                            function from the project's Pipfile (BETA).
        build-docker-image  Build the default 'possum' Docker image to run build
                            jobs within.

The ``package`` Command
^^^^^^^^^^^^^^^^^^^^^^^

Build Lambda packages, upload to S3, and generate a deployment tamplate from
your source template.

::

    $ possum package -h
    usage: possum package [-h] [-t template] [-o output] [-p profile_name] [-c]
                          [--docker] [--docker-image image_name]
                          s3_bucket

    positional arguments:
      s3_bucket             The S3 bucket to upload artifacts. You may optionally
                            pass a path within the bucket to store the Lambda
                            artifacts (defaults to 'possum-{timestamp}').

    optional arguments:
      -h, --help            show this help message and exit
      -t template, --template template
                            The filename of the SAM template.
      -o output, --output-template output
                            Optional filename for the output template.
      -p profile_name, --profile profile_name
                            Optional profile name for AWS credentials.
      -c, --clean           Build all Lambda packages, ignoring previous run.
      --docker              Build Lambda packages within a Docker container
                            environment.
      --docker-image image_name
                            Specify a Docker image to use (defaults to
                            'possum:latest').


::

    $ possum package '<s3-bucket-name>'

The above command will package the Python Lambda functions and upload
them to S3 assuming the template file is named ``template.yaml``. You
can specify the template's name with the ``-t/--template`` argument:

::

    $ possum package '<s3-bucket-name>' -t my-template.yml

The generated deployment template will printed on the screen.

By default, Possum will upload *new* artifacts to a directory in your chosen S3
bucket named ``possum-0123456789`` where the numerical value is the current
timestamp.

If you wish to override this default and specify the directory path to upload
new artifact, append it to the S3 bucket name using forward slashes:

::

    $ possum package '<s3-bucket-name>/<my_path>'

You can also specify the deployment template be written to a file by
passing a name to the ``-o/--output-template`` argument:

::

    $ possum package '<s3-bucket-name>' -o deployment.yaml

Possum uses hashes of your function directories to determine if changes have
occurred since the last run of the command. Hashes and S3 URIs are saved in a
``~/.possum`` directory for each project you package with Possum.

To force Possum to build all functions and skip the hash check, use the
``-c/--clean`` argument.

The ``generate-requirements`` Command (BETA)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

An experimental option for generating and maintaining ``requirements.txt`` files
for each Lambda function in the template based upon the project's root Pipfile.

::

    $ possum generate-requirements -h
    usage: possum generate-requirements [-h] [-t template]

    optional arguments:
      -h, --help            show this help message and exit
      -t template, --template template
                            The filename of the SAM template.

This command attempts to determine required packages by parsing ``import``
statements from the Lambda handler file for the function as defined within the
template.

::

    $ possum generate-requirements
    Evaluating Lambda function dependencies...

    WebLambda: A requirements.txt file has been generated with the following packages:
    WebLambda: jinja2==2.10

    ApiLambda: A requirements.txt file has been generated with the following packages:
    ApiLambda: cryptography==2.2.2, jsonschema==2.6.0

    SimpleLambda: No requirements.txt file generated

    OtherLambda: A requirements.txt file has been generated with the following packages:
    OtherLambda: git+https://github.com/brysontyrrell/MyPackage.git#egg=mypackage

This functionality is experimental and subject to change.

AWS Credentials
---------------

Possum uses the Boto3 SDK for uploading artifacts to S3. You can set your
AWS access and secret keys in your environment variables as described in
the Boto3 documentation. Possom also accepts a profile name for your AWS
credentials file via the ``-p/--profile`` argument.

::

    $ possum package '<s3-bucket-name>' --profile '<my-profile-name>'

Docker Support
--------------

The installation of some Python packages differ based on the underlying system
(``cryptography`` is one example). To ensure your installed dependencies are
fully compatible with the Lambda environment, you may opt to run Possum within
a Docker container.

The ``build-docker-image`` Command
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can use Possum to build a basic Docker image with the default
``possum:latest`` tag used by the ``--docker-image`` argument:

::

    $ possum build-docker-image -h
    usage: possum build-docker-image [-h]

    optional arguments:
      -h, --help  show this help message and exit

This image is based upon the included Dockerfile, but will install Possom from
PyPI instead of using the local source.

::

    $ possum build-docker-image
    Building 'possum:1.5.0' Docker image (this may take several minutes)...
    Tagging as 'latest'...
    Image successfully created:
      ID: dd8bec4aae
      Tags: possum:1.5.0, possum:latest

Dockerfile
^^^^^^^^^^

The included ``Dockerfile`` in this project will create a compatible default
image to use. Run the following command from the same directory as the
``Dockerfile`` to build the image:

::

    $ docker build . -t possum:latest

This image is based upon ``lambci/lambda:build-python3.6``. You may build your
own custom image and specify it using the ``--docker-image`` argument. If you
decide to use your own image it must have ``pipenv`` and ``possum`` installed!

Run in Docker
^^^^^^^^^^^^^

Launch Possum in a container using the ``--docker`` argument:

::

    $ possum package '<s3-bucket-name>' --docker

Serverless App Repository Example
---------------------------------

Here is an example of a serverless Python application with multiple Lambda
functions in a single repository:

::

    my_prjoect/
        |
        |__ template.yaml
        |
        |__ function1/
        |   |
        |   |__ function1.py
        |
        |__ function2/
            |
            |__ function2.py
            |__ requirements.txt

For each AWS Lambda function defined in the template, Possum references
the ``Properties:CodeUri`` key for the path to the function's directory.

Possum will display a warning if the function's ``Properties:Runtime``
value does not match ``python*``. You will need to package these remaining
functions separately.

The contents of each functions' directory will be copied to a temporary
build directory. If a ``Pipfile``/``Pipfile.lock`` or ``requirements.txt``
exist, the external packages will be installed into the build directory. The
entire contents of the build directory will then be zipped into a deployable
Lambda artifact.

All artifacts will be uploaded to the provided S3 bucket. The imported
template will be updated with the S3 locations for each Lambda function
and written ``stdout`` or a file if the ``-o`` argument was provided.

The generated deployment template can be used with ``sam deploy`` or
``aws cloudformation deploy`` to deploy the application.
