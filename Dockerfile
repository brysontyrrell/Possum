FROM lambci/lambda:build-python3.6

RUN /var/lang/bin/pip install -U pip && \
    /var/lang/bin/pip install pipenv

ADD ./ /tmp/possum/

RUN cd /tmp/possum && \
    /var/lang/bin/python /tmp/possum/setup.py install && \
    /bin/rm -r /tmp/possum

WORKDIR /var/task
