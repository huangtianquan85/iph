#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import shutil
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


if __name__ == '__main__':
    src = sys.argv[1]

    shrink = 'shrink.zip'
    repack = 'repack.zip'
    unpack_folder = 'tmp'

    if os.path.exists(shrink):
        os.remove(shrink)
    if os.path.exists(repack):
        os.remove(repack)
    if os.path.exists(unpack_folder):
        shutil.rmtree(unpack_folder)

    os.makedirs(unpack_folder)

    src_md5 = get_file_md5(src)
    print(src, src_md5, os.path.getsize(src))

    start = datetime.datetime.now()

    # unpack
    zip_utils.unpack(src, shrink, unpack_folder)
    now = datetime.datetime.now()
    print('unpack use %d seconds' % (now - start).seconds)
    print(shrink, os.path.getsize(shrink))

    # repack
    zip_utils.repack(shrink, repack, unpack_folder)
    now = datetime.datetime.now()
    print('repack use %d seconds' % (now - start).seconds)

    repack_md5 = get_file_md5(repack)
    print(repack, repack_md5, os.path.getsize(repack))

    if src_md5 == repack_md5:
        print('success')
        print('md5: ' + src_md5)
    else:
        print('error')
