#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import struct
import hashlib
import zip_utils


def shrink(src_path, dst_path, item_folder):
    ''' 将原始 zip 包拆分存储
    Args:
        src_path:    原始 zip 包路径
        dst_path:    精简后的 zip 包路径
        item_folder: 文件内容存储路径
    '''

    # 打开源文件
    with open(src_path, 'rb') as f:
        buffer = f.read()

    file_infos = zip_utils.get_file_infos(buffer)

    # 准备输出文件
    dst = open(dst_path, 'wb')

    # 光标，记录上一次处理到的位置
    cursor = 0

    # 遍历所有文件
    for f in file_infos:
        offset = (f.header_offset +
                  zip_utils.get_header_len(buffer, f.header_offset))
        # 写入 cursor 到 offset 之间的数据
        dst.write(buffer[cursor:offset])

        # 处理文件内容
        data = buffer[offset:offset+f.compressed_size]

        # 计算文件内容 hash
        m = hashlib.md5()
        m.update(data)
        hash = m.hexdigest()

        # 写内容到文件
        path = os.path.join(item_folder, hash)
        if not os.path.exists(path):
            with open(path, 'wb') as file:
                file.write(data)

        # 记录 hash
        dst.write(m.digest())

        # 光标置于文件内容区末尾
        cursor = offset + f.compressed_size

    # 写入尾部内容
    dst.write(buffer[cursor:])
    # 关闭文件
    dst.close()
