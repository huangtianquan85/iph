#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import struct
import hashlib
import zip_utils


def repack(src_path, dst_path, item_folder):
    ''' 将精简后的 zip 恢复
    Args:
        src_path:    精简后的 zip 包路径
        dst_path:    恢复后的 zip 包路径
        item_folder: 文件内容存储路径
    '''

    # 打开文件
    with open(src_path, 'rb') as f:
        buffer = f.read()

    file_infos = zip_utils.get_file_infos(buffer)

    # 准备输出文件
    dst = open(dst_path, 'wb')

    # 光标，记录上一次处理到的位置
    cursor = 0
    # 抽出大小，用于修正精简版 zip 中文件头的偏移
    ex_size = 0
    # 遍历所有文件
    for f in file_infos:
        header_offset = f.header_offset - ex_size
        offset = header_offset + \
            zip_utils.get_header_len(buffer, header_offset)
        # 写入 cursor 到 offset 之间的数据
        dst.write(buffer[cursor:offset])

        # 读取记录的内容 hash
        hash = buffer[offset:offset+zip_utils.hash_len].hex()

        # 读取内容并写入恢复文件
        path = os.path.join(item_folder, hash)
        with open(path, 'rb') as file:
            dst.write(file.read())

        # 光标置于文件内容区（此时为 hash）末尾
        cursor = offset + zip_utils.hash_len
        # 偏移修正
        ex_size += f.compressed_size - zip_utils.hash_len

    # 写入尾部内容
    dst.write(buffer[cursor:])
    # 关闭文件
    dst.close()
