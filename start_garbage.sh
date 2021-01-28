#!/bin/bash

export CPPFLAGS=-I/usr/local/opt/openssl/include
export LDFLAGS=-L/usr/local/opt/openssl/lib

cd /home/mulligan/ottawagarbage/src
/usr/bin/gunicorn3 garbage:app
