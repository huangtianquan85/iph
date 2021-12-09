#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import hashlib
import zip_utils
import datetime


def get_file_md5(path):
    m = hashlib.md5()
    with open(path, 'rb') as f:
        while True:
            data = f.read(4096)
            if not data:
                break
            m.update(data)
    return m.hexdigest()


src = 'test.apk'
shrink = 'shrink.apk'
repack = 'repack.apk'
unpack_folder = 'tmp'

if not os.path.exists(unpack_folder):
    os.makedirs(unpack_folder)

src_md5 = get_file_md5(src)

start = datetime.datetime.now()

# unpack
zip_utils.unpack(src, shrink, unpack_folder)
now = datetime.datetime.now()
print('unpack use %d seconds' % (now - start).seconds)

# repack
zip_utils.repack(shrink, repack, unpack_folder)
now = datetime.datetime.now()
print('repack use %d seconds' % (now - start).seconds)

repack_md5 = get_file_md5(repack)

if src_md5 == repack_md5:
    print('success')
    print('md5: ' + src_md5)
else:
    print('error')
