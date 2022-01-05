#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import hashlib
import zip_utils


def shrink(src_path, dst_path, item_folder, content_monitor=None):
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

    # 源文件整体 hash
    src_m = hashlib.md5()

    # 处理区段数据（更新整体 hash，追加数据到目标文件）
    def handle_seg(data, append=True):
        # 更新 hash
        src_m.update(data)
        # 追加数据到目标文件
        if append:
            dst.write(data)

    # 光标，记录上一次处理到的位置
    cursor = 0
    # 遍历所有文件
    for f in file_infos:
        # 计算偏移
        offset = (f.header_offset +
                  zip_utils.get_header_len(buffer, f.header_offset))

        # 处理上一个处理位置到此头结构末尾的部分
        handle_seg(buffer[cursor:offset])

        # 处理文件内容
        data = buffer[offset:offset+f.compressed_size]
        handle_seg(data, append=False)

        # 计算文件内容 hash
        m = hashlib.md5()
        m.update(data)
        hash = m.hexdigest()

        # 写内容到文件
        path = os.path.join(item_folder, hash)
        if not os.path.exists(path):
            with open(path, 'wb') as file:
                file.write(data)

        if content_monitor != None:
            content_monitor(f.name, hash)

        # 记录 hash
        dst.write(m.digest())

        # 光标置于文件内容区末尾
        cursor = offset + f.compressed_size

    # 处理尾部内容
    handle_seg(buffer[cursor:])
    # 写入源文件 hash
    hash = src_m.digest()
    dst.write(hash)

    # 关闭文件
    dst.close()

    return hash
