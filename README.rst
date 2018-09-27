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

AWS Credentials
---------------

Possum uses the Boto3 SDK for uploading artifacts to S3. You can set your
AWS access and secret keys in your environment variables as described in
the Boto3 documentation. Possom also accept a profile name for your AWS
credentials file via the ``-p/--profile`` argument.

::

    $ possum '<s3-bucket-name>' --profile '<my-profile-name>'

Basic Usage
-----------

Run Possum from the repository directory containing the serverless
application.

::

    $ possum '<s3-bucket-name>'

The above command will package the Python Lambda functions and upload
them to S3 assuming the template file is named ``template.yaml``. You
can specify the template's name with the ``-t/--template`` argument:

::

    $ possum '<s3-bucket-name>' -t my-template.yml

The generated deployment template will printed on the screen.

By default, Possum will upload *new* artifacts to a directory in your chosen S3
bucket named ``possum-0123456789`` where the numerical value is the current
timestamp.

If you wish to override this default and specify the directory path to upload
new artifact, append it to the S3 bucket name using forward slashes:

::

    $ possum '<s3-bucket-name>/<my_path>'

You can also specify the deployment template be written to a file by
passing a name to the ``-o/--output-template`` argument:

::

    $ possum '<s3-bucket-name>' -o deployment.yaml

Possum uses hashes of your function directories to determine if changes have
occurred since the last run of the command. Hashes and S3 URIs are saved in a
``~/.possum`` directory for each project you package with Possum.

To force Possum to build all functions and skip the hash check, use the
``-c/--clean`` argument.

You can view the options and instructions for using Possum with the
``-h`` argument:

::

    $ possum -h
    usage: possum [-h] [-t template] [-o output] [-p profile_name] [-c] [--docker]
              [--docker-image image_name] [-v]
              s3_bucket

    Possum is a utility to package Python-based serverless applications using the
    Amazon Serverless Application model with per-function dependencies.

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
      -v, --version         Display version information.

Docker Support
--------------

The installation of some Python packages differ based on the underlying system
(cryptography.io is an example). To ensure your installed dependencies are
fully compatible with the Lambda environment, you may opt to run Possum within
a Docker container.

The included ``Dockerfile`` in this project will create a compatible default
image to use. Run the following command from the same directory as the
``Dockerfile`` to build the image:

::

    $ docker build . -t possum:latest

This image is based upon ``lambci/lambda:build-python3.6``. You may build your
own custom image and specify it using the ``--docker-image`` argument. If you
decide to use your own image it must have ``pipenv`` and ``possum`` installed!

Launch Possum in a container using the ``--docker`` argument:

::

    $ possum '<s3-bucket-name>' --docker

Serverless App Repository Example
---------------------------------

Here is an example of a serverless Python application with multiple Lambda
functions in a single repository:

::

    my_prjoect/
        |
        |___template.yaml
        |
        |___function1/
        |   |
        |   |___function1.py
        |
        |___function2/
            |
            |___function2.py
            |___Pipfile
            |___Pipfile.lock

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
