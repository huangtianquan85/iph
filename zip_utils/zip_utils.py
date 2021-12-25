#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import struct
import hashlib


# 内容抽出的阈值，先用 4k 试试，参考文件读写经验数值
threshold = 4096

'''
参考资源
https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT
https://en.wikipedia.org/wiki/ZIP_(file_format)
'''


class FileInfo(object):
    '''
    0   central file header signature   4 bytes  (0x02014b50)
    1   version made by                 2 bytes
    2   version needed to extract       2 bytes
    3   general purpose bit flag        2 bytes
    4   compression method              2 bytes
    5   last mod file time              2 bytes
    6   last mod file date              2 bytes
    7   crc-32                          4 bytes
    8   compressed size                 4 bytes  (压缩后大小)
    9   uncompressed size               4 bytes
    10  file name length                2 bytes  (文件名长度)
    11  extra field length              2 bytes  (扩展区长度)
    12  file comment length             2 bytes  (注释长度)
    13  disk number start               2 bytes
    14  internal file attributes        2 bytes
    15  external file attributes        4 bytes
    16  relative offset of local header 4 bytes  (文件存储区头结构偏移)

        file name (variable size)
        extra field (variable size)
        file comment (variable size)
    '''

    struct_sign = '<4s6H3L5H2L'
    fixed_len = struct.calcsize(struct_sign)
    sign = b'PK\001\002'

    def __init__(self, buffer, offset):
        self.match_sign = buffer[offset:offset+4] == self.sign
        if not self.match_sign:
            return

        data = struct.unpack(self.struct_sign,
                             buffer[offset:offset+self.fixed_len])
        self.compressed_size = data[8]
        name_len = data[10]
        self.name = buffer[offset+self.fixed_len:
                           offset+self.fixed_len+name_len].decode('utf-8')
        self.header_offset = data[16]
        self.info_len = self.fixed_len + name_len + data[11] + data[12]


def parse_directory(buffer, dir_offset, dir_size):
    ''' 遍历中央目录中的所有文件信息
    Args:
        buffer: 源文件字节数组
        dir_offset: 中央目录偏移
        dir_size: 中央目录大小
    '''

    file_infos = []
    offset = dir_offset
    end = dir_offset + dir_size
    while offset < end:
        f = FileInfo(buffer, offset)
        # 过滤掉小于 4k 的文件
        if (f.compressed_size > threshold):
            file_infos.append(f)
        offset += f.info_len

    # 按偏移量排序（中央目录不保证顺序，但不会有两个文件共用存储，结构上就不支持）
    '''
    From Wikipedia Zip Format:
    The order of the file entries in the central directory 
    need not coincide with the order of file entries in the archive
    '''
    file_infos.sort(key=lambda x: x.header_offset)
    return file_infos


def parse_EOCD(buffer):
    ''' 解析中央目录结束标记，返回中央目录偏移和大小
        重点: **中央目录中文件信息是连续的，且其后紧跟结束标记（zip64 除外，本项目暂不支持 zip64）**
        因为中央目录结束标记中记录的中央目录偏移是针对文件头的编译
        所以精简版 zip 这个偏移无法命中，也无法计算（需要先解析中央目录）
        只能这样计算: 中央目录结束标记偏移 - 目录大小

    End of central directory record

    0   end of central dir signature    4 bytes  (0x06054b50)
    1   number of this disk             2 bytes
    2   number of the disk with the
        start of the central directory  2 bytes
    3   total number of entries in the
        central directory on this disk  2 bytes
    4   total number of entries in
        the central directory           2 bytes
    5   size of the central directory   4 bytes  (中央目录大小)
    6   offset of start of central
        directory with respect to
        the starting disk number        4 bytes
    7   .ZIP file comment length        2 bytes
    8   .ZIP file comment               (variable size)

    Args:
        buffer: 源文件字节数组
    '''

    struct_sign = '<4s4H2LH'
    fixed_len = struct.calcsize(struct_sign)
    sign = b'PK\005\006'

    # 起始搜索位置近似值
    offset = len(buffer) - fixed_len
    while offset > 0:
        if buffer[offset:offset+4] != sign:
            offset -= 1
            continue
        data = struct.unpack(struct_sign, buffer[offset:offset+fixed_len])
        return data[5], offset - data[5]
    return -1, -1


def get_header_len(buffer, offset):
    ''' Get local file header total length

    0   local file header signature     4 bytes  (0x04034b50)
    1   version needed to extract       2 bytes
    2   general purpose bit flag        2 bytes
    3   compression method              2 bytes
    4   last mod file time              2 bytes
    5   last mod file date              2 bytes
    6   crc-32                          4 bytes
    7   compressed size                 4 bytes
    8   uncompressed size               4 bytes
    9   file name length                2 bytes  (文件名长度)
    10  extra field length              2 bytes  (扩展区长度)

        file name (variable size)
        extra field (variable size)
    '''

    struct_sign = '<4s5H3L2H'
    fixed_len = struct.calcsize(struct_sign)
    sign = b'PK\003\004'
    data = struct.unpack(struct_sign, buffer[offset:offset+fixed_len])
    return fixed_len + data[9] + data[10]


def do(src_path, dst_path, handler):
    ''' 遍历 zip 包内所有头结构并执行相应处理
    Args:
        src_path: 源 zip 包路径
        dst_path: 目标 zip 包路径
        handler:  处理方法
    '''

    # 打开文件
    with open(src_path, 'rb') as f:
        buffer = f.read()

    dir_size, dir_offset = parse_EOCD(buffer)
    file_infos = parse_directory(buffer, dir_offset, dir_size)

    # 准备输出文件
    dst = open(dst_path, 'wb')

    # 光标，记录上一次处理到的位置
    cursor = 0
    # 抽出大小，用于修正精简版 zip 中文件头的偏移
    ex_size = 0
    # 遍历所有文件
    for f in file_infos:
        header_offset = f.header_offset - ex_size
        offset = header_offset + get_header_len(buffer, header_offset)
        # 写入 cursor 到 offset 之间的数据
        dst.write(buffer[cursor:offset])
        # 处理文件内容
        size, fix_offset = handler(buffer, offset, f.compressed_size, dst)
        # 光标置于文件内容区末尾（由抽出/合并方法来计算）
        cursor = offset + size
        # 偏移修正
        ex_size += fix_offset

    # 写入尾部内容
    dst.write(buffer[cursor:])
    # 关闭文件
    dst.close()


def unpack(src_path, dst_path, item_folder):
    ''' 将原始 zip 包拆分存储
    Args:
        src_path:    原始 zip 包路径
        dst_path:    精简后的 zip 包路径
        item_folder: 文件内容存储路径
    '''

    def handler(buffer, offset, compressed_size, dst):
        ''' 处理单个文件
        Args:
            buffer: 原始 zip 文件字节数组
            offset: 压缩内容偏移
            compressed_size: 压缩后大小
            dst: 精简后的 zip 文件句柄
        '''
        data = buffer[offset:offset+compressed_size]

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

        # 返回处理的数据大小，偏移修正量
        return compressed_size, 0

    return do(src_path, dst_path, handler)


def repack(src_path, dst_path, item_folder):
    ''' 将精简后的 zip 恢复
    Args:
        src_path:    精简后的 zip 包路径
        dst_path:    恢复后的 zip 包路径
        item_folder: 文件内容存储路径
    '''

    hash_len = 16

    def handler(buffer, offset, compressed_size, dst):
        ''' 处理单个文件
        Args:
            buffer: 精简后的 zip 文件字节数组
            offset: 压缩内容偏移
            compressed_size: 压缩后大小
            dst: 恢复后的 zip 文件句柄
        '''

        # 读取 hash
        hash = buffer[offset:offset+hash_len].hex()

        # 读取内容并写入恢复文件
        path = os.path.join(item_folder, hash)
        with open(path, 'rb') as f:
            dst.write(f.read())

        # 返回处理的数据大小，偏移修正量
        return hash_len, compressed_size - hash_len

    return do(src_path, dst_path, handler)
