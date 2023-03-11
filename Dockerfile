FROM python:3.11-alpine

WORKDIR /usr/src/app

ADD . .

RUN python setup.py develop


CMD dyn_gandi
