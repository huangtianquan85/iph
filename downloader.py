#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import hashlib
import time
import zip_utils
import zip_repack
import argparse
from urllib.parse import urlparse
import requests
import threading


lock = threading.Lock()


# 下载项数据结构
class DownloadInfo(object):
    def __init__(self, hash, file_info):
        self.hash = hash
        self.file_info = file_info
        self.state = 'wait'
        self.retry = 0


# 获取文件 MD5
def get_file_md5(path):
    m = hashlib.md5()
    with open(path, 'rb') as f:
        while True:
            data = f.read(4096)
            if not data:
                break
            m.update(data)
    return m.hexdigest()


# 获取二进制内容 MD5
def get_buffer_md5(buffer):
    m = hashlib.md5()
    m.update(buffer)
    return m.hexdigest()


# 解析 shrink 包
def parse_shrink_package(buffer, item_folder):
    ''' 分析精简后的 zip 包
    Args:
        buffer:    精简后的 zip 包二进制
        item_folder: 文件内容存储路径
    '''

    downloads = []

    # 抽取原始压缩文件 hash
    origin_md5 = buffer[-zip_utils.hash_len:].hex()
    buffer = buffer[:-zip_utils.hash_len]

    file_infos = zip_utils.get_file_infos(buffer)

    # 抽出大小，用于修正精简版 zip 中文件头的偏移
    ex_size = 0
    # 遍历所有文件
    for f in file_infos:
        header_offset = f.header_offset - ex_size
        offset = (header_offset +
                  zip_utils.get_header_len(buffer, header_offset))

        # 读取记录的内容 hash
        hash = buffer[offset:offset+zip_utils.hash_len].hex()

        # 查找是否被缓存
        path = os.path.join(item_folder, hash)
        if not os.path.exists(path):
            downloads.append(DownloadInfo(hash, f))

        # 偏移修正
        ex_size += f.compressed_size - zip_utils.hash_len

    return downloads, origin_md5


# 轮询下载
def download_next(downloads, base_url, item_folder):
    def get_next():
        lock.acquire()

        next = None
        for d in downloads:
            if d.state == 'wait':
                d.state = 'downloading'
                next = d
                break

        lock.release()
        return next

    while True:
        next = get_next()
        if next == None:
            break

        hash = next.hash

        try:
            r = requests.get(base_url + '/blocks/' + hash)
            if r.status_code != 200:
                raise Exception('error: status_code: %d' % r.status_code)

            h = get_buffer_md5(r.content)
            if h != hash:
                raise Exception('error: md5 not match')

            path = os.path.join(item_folder, hash)
            with open(path, 'wb') as f:
                f.write(r.content)
            print('downloaded: %s %s' % (hash, next.file_info.name))

            lock.acquire()
            next.state = 'done'
            lock.release()

        except Exception as e:
            print(e)

            lock.acquire()
            if next.retry > 2:
                print('retry fail' + hash)
                next.state = 'fail'
            else:
                print('retry ' + hash)
                next.retry += 1
                next.state = 'wait'
            lock.release()


# 下载队列监控
def monitor(downloads):
    while True:
        time.sleep(1)
        all_done = True
        has_error = False
        for d in downloads:
            if d.state == 'done':
                continue
            if d.state == 'fail':
                has_error = True
                continue
            all_done = False
            break

        if all_done:
            break
    return has_error


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='PROG')
    parser.add_argument('url', help='shrink package url')
    parser.add_argument('-c', '--cache', help='cache folder')
    parser.add_argument('-o', '--output', help='output file path or folder')
    args = parser.parse_args()

    # 创建缓存目录
    if args.cache == None:
        blocks_folder = 'cache'
    else:
        blocks_folder = args.cache

    if not os.path.exists(blocks_folder):
        os.mkdir(blocks_folder)

    # 解析 url
    url = args.url
    file_name = url.split('/')[-1]

    # 下载精简 zip 包
    shrink_pkg_path = 'shrink-' + file_name
    r = requests.get(url)
    with open(shrink_pkg_path, 'wb') as f:
        f.write(r.content)

    # 解析精简 zip 包并获取下载列表
    downloads, origin_md5 = parse_shrink_package(r.content, blocks_folder)
    print('%d blocks need to download' % len(downloads))

    # 开 5 个线程下载
    base_url = url[0:-len(urlparse(url).path)]
    for i in range(5):
        t = threading.Thread(target=download_next, args=(
            downloads, base_url, blocks_folder))
        t.start()

    # 开启下载监控
    m = threading.Thread(target=monitor, args=(downloads,))
    m.start()
    m.join()

    output_path = args.output
    if output_path == None:
        dst_path = file_name
    elif os.path.splitext(output_path)[1] == '':
        dst_path = os.path.join(output_path, file_name)
    else:
        dst_path = output_path

    print('repacking...')

    # repack
    zip_repack.repack(shrink_pkg_path, dst_path, blocks_folder)
    # clean shrink package
    os.remove(shrink_pkg_path)

    # 校验 md5
    repack_md5 = get_file_md5(dst_path)
    print('origin md5 => ' + origin_md5)
    print('repack md5 => ' + repack_md5)
    if repack_md5 != origin_md5:
        print('md5 check fail')
        exit(1)

    print('all done')
