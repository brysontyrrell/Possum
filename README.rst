Possum
======

*Python AWS SAM* --> *PyAWSSAM* --> *Pawssam* --> **Possum**

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

Run Possum from the repository directory containing the serverless
application.

::

    $ python /path/to/possum.py '<s3-bucket-name>'

The above command will package the Python Lambda functions and upload
them to S3 assuming the template file is named ``template.yaml``. You
can specify the template's name with the ``-t/--template`` argument:

::

    $ python /path/to/possum.py '<s3-bucket-name>' -t my-template.yml

The generated deployment template will printed on the screen.

You can also specify the deployment template be written to a file by
passing a name to the ``-o/--output-template`` argument:

::

    $ python /path/to/possum.py '<s3-bucket-name>' -o deployment.yaml

You can view the options and instructions for using Possum with the
``-h`` argument:

::

    $ python /path/to/possum.py -h
    usage: possum [-h] [-t template] [-o output] s3_bucket

    Possum is a utility to package and deploy Python-based serverless applications
    using the Amazon Serverless Application model with per-function dependencies
    using Pipfiles.

    positional arguments:
      s3_bucket             The S3 bucket to upload artifacts

    optional arguments:
      -h, --help            show this help message and exit
      -t template, --template template
                            The filename of the SAM template
      -o output, --output-template output
                            Optional filename for the output template

Repository Structure
--------------------

Possum is designed around a serverless application existing entirely
within a single repository.

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

At the root level of the repository is the ``template.yaml`` file for
CloudFormation.

For each AWS Lambda function defined in the template, Possum references
the ``Properties:CodeUri`` key for the path to the function's directory.
Possum will exit with an error if the function's ``Properties:Runtime``
value does not match ``python*``.

The contents of each functions' directory will be copied to a temporary
build directory. If a ``Pipfile`` and ``Pipfile.lock`` exist, the
external packages will be installed into the build directory. The entire
contents of the build directory will then be zipped into a deployable
Lambda artifact.

All artifacts will be uploaded to the provided S3 bucket. The imported
template will be updated with the S3 locations for each Lambda function
and written ``stdout`` or a file if the ``-o`` argument was provided.

The generated deployment template can be used with ``sam deploy`` or
``aws cloudformation deploy`` to deploy the application.
