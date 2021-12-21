#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import struct
import hashlib


# 内容抽出的阈值，先用 4k 试试，参考文件读写经验数值
threshold = 4096


"""
0	4	local file header signature	文件头标识(固定值0x04034b50)
4	2	version needed to extract	解压时遵循ZIP规范的最低版本
6	2	general purpose bit flag	通用标志位
8	2	compression method	压缩方式
10	2	last mod file time	最后修改时间（MS-DOS格式）
12	2	last mod file date	最后修改日期（MS-DOS格式）
14	4	crc-32	冗余校验码
18	4	compressed size	压缩后的大小
22	4	uncompressed size	未压缩之前的大小
26	2	file name length	文件名长度（n）
28	2	extra field length	扩展区长度（m）
30	n	file name	文件名
30+n	m	extra field	扩展区
"""


# 头结构
structFileHeader = "<4s2B4HL2L2H"
# 头结构固定区大小
sizeFileHeader = struct.calcsize(structFileHeader)
# 头结构标识
stringFileHeader = b"PK\003\004"
# 头结构标识大小
sizeFileHeaderMagic = len(stringFileHeader)


class FileHeadInfo(object):
    def __init__(self, zip, offset):
        # 文件内偏移量
        self.offset = offset

        # 按偏移量定位
        zip.seek(offset)

        # 解析头结构
        data = zip.read(sizeFileHeader)
        head = struct.unpack(structFileHeader, data)

        # 判断是否是文件头
        self.is_file = head[0] == stringFileHeader

        if not self.is_file:
            return

        # 解析文件名，从头结构末尾开始
        zip.seek(offset + sizeFileHeader)
        name_len = head[10]
        self.file_name = zip.read(name_len).decode('utf-8')

        # 计算头结构总长，头固定长 + 文件名长 + 扩展区长
        self.head_len = sizeFileHeader + name_len + head[11]

        # TODO: 判断并获取 zip64 内容大小
        # 记录内容长度
        self.data_len = head[8]


def is_file_entry(file, offset):
    file.seek(offset)
    m = file.read(sizeFileHeaderMagic)
    return m == stringFileHeader


def do(src_path, dst_path, handler):
    ''' 遍历 zip 包内所有头结构并执行相应处理
    Args:
        src_path: 源 zip 包路径
        dst_path: 目标 zip 包路径
        handler:  处理方法
    '''

    # 获取 src 文件大小
    src_size = os.path.getsize(src_path)

    # 打开文件
    src = open(src_path, 'rb')
    dst = open(dst_path, 'wb')

    # 遍历所有头结构
    last_offset = 0
    offset = 0
    while offset < src_size - sizeFileHeader:
        if not is_file_entry(src, offset):
            offset += 1
            continue

        head = FileHeadInfo(src, offset)
        if head.data_len < threshold:
            # 小于阈值的直接写入，不做抽出/合并处理
            offset += head.head_len + head.data_len
        else:
            # 大于阈值先写入头结构
            offset += head.head_len

        # 写入 last_offset 到 offset 之间的数据
        src.seek(last_offset)
        dst.write(src.read(offset - last_offset))

        if head.data_len >= threshold:
            # 抽出/合并内容部分，并获得下一个头结构的偏移
            offset = handler(src, dst, head)

        last_offset = offset

    # 写入尾部内容
    src.seek(last_offset)
    dst.write(src.read(src_size - last_offset))

    # 关闭文件
    src.close()
    dst.close()


def unpack(src_path, dst_path, item_folder):
    ''' 将原始 zip 包拆分存储
    Args:
        src_path:    原始 zip 包路径
        dst_path:    精简后的 zip 包路径
        item_folder: 文件内容存储路径
    '''

    def handler(src, dst, head):
        ''' 处理单个文件
        Args:
            src:  原始 zip 文件句柄
            dst:  精简后的 zip 文件句柄
            head: 头信息
        '''

        # 定位到头结构末尾
        src.seek(head.offset + head.head_len)

        # 读取内容
        data = src.read(head.data_len)

        # 计算 hash
        m = hashlib.md5()
        m.update(data)
        hash = m.hexdigest()

        # 写内容到文件
        path = os.path.join(item_folder, hash)
        if not os.path.exists(path):
            with open(path, 'wb') as f:
                f.write(data)

        # 记录 hash
        dst.write(m.digest())

        # 返回下一个头结构的偏移
        return head.offset + head.head_len + head.data_len

    return do(src_path, dst_path, handler)


def repack(src_path, dst_path, item_folder):
    ''' 将精简后的 zip 恢复
    Args:
        src_path:    精简后的 zip 包路径
        dst_path:    恢复后的 zip 包路径
        item_folder: 文件内容存储路径
    '''

    hash_len = 16

    def handler(src, dst, head):
        ''' 处理单个文件
        Args:
            src:  精简后的 zip 文件句柄
            dst:  恢复后的 zip 文件句柄
            head: 头信息
        '''

        # 读取 hash
        src.seek(head.offset + head.head_len)
        hash = src.read(hash_len).hex()

        # 读取内容并写入恢复文件
        path = os.path.join(item_folder, hash)
        with open(path, 'rb') as f:
            dst.write(f.read())

        # 返回下一个头结构的偏移
        return head.offset + head.head_len + hash_len

    return do(src_path, dst_path, handler)
