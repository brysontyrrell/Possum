# Possum

*Python AWS SAM* --> *PyAWSSAM* --> *Pawssam* --> **Possum**

## About

Possum is a packaging tool for serverless Python-based applications using the AWS Serverless Application Model (AWS SAM).

The `sam package` or `aws cloudformation package` options have a severe limitation when it comes to Python AWS Lambda functions: they have no means of packaging a function that has external dependencies. This means that developers are always on their own for creating those Lambda artifacts, uploading them to S3, and deploying.

Possum aims to server as a replacement to the basic package functions. The tool is based upon my approach to serverless AWS applications (opinionated) and may not be a fit for all parties.

## Basic Usage

Run Possum from the repository directoy containing the serverless application.

```
~$ python /path/to/possum.py
```

## Repository Structure

Possum is designed around a serverless application existing entirely within a single repository.

```
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
```

At the root level of the repository is the `template.yaml` file for CloudFormation.

For each AWS Lambda function defined in the template, Possum expects a directory matching the template keyname. If the directory contains a `Pipfile` and `Pipfile.lock` the contents will be copied to a temp directoy, the packages installed locally, and the zip artifact created. Directories that only contain the Python file for the Lambda function will also have their zip artifacts created.

All zip artifacts will be uploaded to the specified S3 bucket. The imported template will be updated with the S3 locations for each Lambda function and written to both stdout and a `deployment-template.yaml` file read to be used with `sam deploy` or `aws cloudformation deploy`.