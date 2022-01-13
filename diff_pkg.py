#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import zip_shrink


if __name__ == '__main__':
    pkg_a = sys.argv[1]
    pkg_b = sys.argv[2]

    a_files = {}

    def monitor_a(f_info, hash):
        a_files[f_info.name] = hash

    def monitor_b(f_info, hash):
        if f_info.name not in a_files:
            print('new  => %d\t%s' %
                  (f_info.compressed_size, f_info.name))
        elif hash != a_files[f_info.name]:
            print('diff => %d\t%s' %
                  (f_info.compressed_size, f_info.name))

    a_md5 = zip_shrink.shrink(pkg_a, '/dev/null', '/dev/null',
                              content_monitor=monitor_a)
    b_md5 = zip_shrink.shrink(pkg_b, '/dev/null', '/dev/null',
                              content_monitor=monitor_b)

    print('%s => %s' % (pkg_a, a_md5.hex()))
    print('%s => %s' % (pkg_b, b_md5.hex()))
