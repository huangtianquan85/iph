#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import hashlib
import zip_shrink
import zip_repack
import json
from collections import OrderedDict
import subprocess
import argparse


# 获取 Shell 命令输出
def shell_output(command):
    try:
        return subprocess.check_output(command, shell=True).decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        return ''


# 加载JSON
def read_json(path):
    with open(path, 'r') as f:
        return json.load(f, object_pairs_hook=OrderedDict)


# 写入JSON
def write_json(json_data, path):
    with open(path, 'w') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2,
                  separators=(',', ': '), sort_keys=True)


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


def get_commit_infos():
    branch = shell_output('git rev-parse --abbrev-ref HEAD')
    hash = shell_output('git rev-parse HEAD')[:8]
    author = shell_output('git --no-pager show -s --format="%an" HEAD')
    date_time = shell_output('git --no-pager show -s --format="%ci" HEAD')
    timestamp = int(shell_output('git --no-pager show -s --format="%ct" HEAD'))
    msg = shell_output('git --no-pager show -s --format="%s" HEAD')

    return {
        "project": project,
        "branch": branch,
        "short_id": hash,
        'author': author,
        'datetime': date_time,
        'timestamp': timestamp,
        "msg": msg,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='PROG')
    parser.add_argument('proj', help='project name')
    parser.add_argument('file', help='package file path')
    parser.add_argument('-c', '--commit-info', help='commit info file path')
    parser.add_argument('-sc', '--save-commit-info',
                        help='save commit info file',
                        action='store_true')
    parser.add_argument('-l', '--last',
                        help='create last commit info file',
                        action='store_true')
    parser.add_argument('-t', '--tag', help='addition tag')
    args = parser.parse_args()

    # 项目名称
    project = args.proj
    # 构建包
    pkg_path = args.file

    # 获取 git 提交信息
    if args.commit_info == None:
        commit = get_commit_infos()
    else:
        commit = read_json(args.commit_info)

    '''
    目录结构
    upload
        last-<项目>-<分支>.commit
        <项目>-<分支>
            2022-01-01-<git_hash>.commit
            2022-01-01-<git_hash>.apk
            2022-01-01-<git_hash>.apk.meta
            2022-01-01-<git_hash>.ipa
            2022-01-01-<git_hash>.ipa.meta
            ...
        blocks
            <md5>
            ...
    '''

    # 各种路径
    base_folder = 'upload'
    blocks_folder = os.path.join(base_folder, 'blocks')
    # 项目-分支
    proj_branch = '%s-%s' % (project, commit['branch'])
    index_folder = os.path.join(base_folder, proj_branch)
    # 日期-git_Hash
    date = commit['datetime'][:10]
    date_hash = '%s-%s' % (date, commit['short_id'])
    commit_path = os.path.join(index_folder, date_hash + '.commit')
    tag = '' if args.tag == None else ('.' + args.tag)
    shrink_pkg_name = date_hash + tag + os.path.splitext(pkg_path)[1]
    shrink_pkg_path = os.path.join(
        index_folder, shrink_pkg_name)
    last_commit_path = os.path.join(
        base_folder, 'last-%s-%s.commit' % (proj_branch, date_hash))
    meta_path = shrink_pkg_path + '.meta'
    # 测试文件
    tmp = os.path.join(base_folder, 'tmp')

    meta = {
        "url": os.path.join(proj_branch, shrink_pkg_name),
        "size": os.path.getsize(pkg_path),
        "icon": ""
    }

    # 重建上传目录
    if os.path.exists(base_folder):
        shutil.rmtree(base_folder)
    os.makedirs(blocks_folder)
    os.makedirs(index_folder)

    def monitor(f_info, hash):
        if f_info.name == 'res/mipmap-xxhdpi-v4/app_icon.png':
            meta['icon'] = os.path.relpath(
                os.path.join(blocks_folder, hash), base_folder)

    # unpack
    src_md5 = zip_shrink.shrink(pkg_path, shrink_pkg_path, blocks_folder,
                                content_monitor=monitor)
    src_md5 = src_md5.hex()
    print(src_md5)

    # repack
    zip_repack.repack(shrink_pkg_path, tmp, blocks_folder)
    repack_md5 = get_file_md5(tmp)
    print(repack_md5)

    if src_md5 != repack_md5:
        print('repack md5 not match source package')
        exit(1)

    os.remove(tmp)
    if args.save_commit_info:
        write_json(commit, commit_path)
    if args.last:
        write_json(commit, last_commit_path)
    write_json(meta, meta_path)
    print('success')
