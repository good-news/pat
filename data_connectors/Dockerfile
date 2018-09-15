FROM amazonlinux

COPY ./requirements.txt requirements.txt 

RUN yum update -y

RUN yum install -y \
   freetds-devel

RUN yum install -y \
    gcc \
    python36 \ 
    gcc-c++ \
    python36-devel

RUN curl -O https://bootstrap.pypa.io/get-pip.py

RUN python3 get-pip.py

RUN pip install Cython && pip install -r requirements.txt