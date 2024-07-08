#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import shutil
import hashlib
import zip_utils
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


def get_commit_infos(project):
    branch = shell_output('git rev-parse --abbrev-ref HEAD')
    branch = branch.replace('/', '_')
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


def mkdirs(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)


def unpack_and_check(origin_pkg, shrink_pkg, blocks_folder, content_monitor):
    # unpack
    src_md5 = zip_shrink.shrink(origin_pkg, shrink_pkg, blocks_folder,
                                content_monitor=content_monitor)
    src_md5 = src_md5.hex()
    print(src_md5)

    # repack
    tmp = 'repack_test.zip'
    zip_repack.repack(shrink_pkg, tmp, blocks_folder)
    repack_md5 = get_file_md5(tmp)
    os.remove(tmp)
    print(repack_md5)

    if src_md5 != repack_md5:
        print('repack md5 not match source package')
        exit(1)


def unpack_by_git(pkg_path, base_folder, blocks_folder, args):
    # 项目
    project = args.project

    # 获取 git 提交信息
    if args.commit_info == None:
        commit = get_commit_infos(project)
    else:
        commit = read_json(args.commit_info)

    '''
    目录结构
    upload
        last-<项目>-<分支>.commit
        <项目>-<分支>
            commits
                2022-01-01-<git_hash>.commit
            metas
                2022-01-01-<git_hash>.apk.meta
                2022-01-01-<git_hash>.ipa.meta
            2022-01-01-<git_hash>.apk
            2022-01-01-<git_hash>.ipa
            ...
        blocks
            <md5>
            ...
    '''

    # 项目-分支
    proj_branch = '%s-%s' % (project, commit['branch'])

    # 构建目录结构
    index_folder = os.path.join(base_folder, proj_branch)
    commits_folder = os.path.join(index_folder, 'commits')
    metas_folder = os.path.join(index_folder, 'metas')
    mkdirs(commits_folder)
    mkdirs(metas_folder)

    # 日期-git_Hash
    date = commit['datetime'][:10]
    date_hash = '%s-%s' % (date, commit['short_id'])
    commit_path = os.path.join(commits_folder, date_hash + '.commit')
    tag = '' if args.tag == None else ('.' + args.tag)
    shrink_pkg_name = date_hash + tag + os.path.splitext(pkg_path)[1]
    shrink_pkg_path = os.path.join(
        index_folder, shrink_pkg_name)
    last_commit_path = os.path.join(
        base_folder, 'last-%s-%s.commit' % (proj_branch, date_hash))
    meta_path = os.path.join(
        metas_folder, shrink_pkg_name + '.meta')

    meta = {
        "url": os.path.join(proj_branch, shrink_pkg_name),
        "size": os.path.getsize(pkg_path),
        "icon": ""
    }

    def monitor(f_info, hash):
        if f_info.name == 'res/mipmap-xxhdpi-v4/app_icon.png':
            meta['icon'] = os.path.relpath(
                os.path.join(blocks_folder, hash), base_folder)

    unpack_and_check(pkg_path, shrink_pkg_path, blocks_folder, monitor)

    if args.save_commit_info:
        write_json(commit, commit_path)
    if args.last:
        write_json(commit, last_commit_path)
    if not args.no_meta:
        write_json(meta, meta_path)


def unpack_blocks_only(pkg_path, base_folder, blocks_folder, shrink_pkg_name):
    if shrink_pkg_name != None:
        shrink_pkg_folder = os.path.join(base_folder, 'pkgs')
        mkdirs(shrink_pkg_folder)
        shrink_pkg_path = os.path.join(shrink_pkg_folder, shrink_pkg_name + '.zip')
    else:
        shrink_pkg_path = 'shrink_tmp.zip'

    unpack_and_check(pkg_path, shrink_pkg_path, blocks_folder, None)

    if shrink_pkg_name == None:
        os.remove(shrink_pkg_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(prog='unpacker.py')
    parser.add_argument('package', help='package file path')
    parser.add_argument('--threshold', type=int, help='set threshold')
    parser.add_argument('--no-clean',
                        help='not clean upload folder',
                        action='store_true')

    blocks_only_group = parser.add_argument_group(
        title='Blocks only options')
    blocks_only_group.add_argument('--blocks-only',
                                   help='without git commit infos',
                                   action='store_true')
    blocks_only_group.add_argument('--shrink-pkg-name',
                                   help='blocks-only mode shrink zip name')

    by_git_group = parser.add_argument_group(
        title='By git commit info options')
    by_git_group.add_argument('--project', help='project name')
    by_git_group.add_argument('--commit-info', help='commit info file path')
    by_git_group.add_argument('--save-commit-info',
                              help='save commit info file',
                              action='store_true')
    by_git_group.add_argument('--last',
                              help='create last commit info file',
                              action='store_true')
    by_git_group.add_argument('--no-meta',
                              help='not create meta file',
                              action='store_true')
    by_git_group.add_argument('--tag', help='addition tag')

    args = parser.parse_args()

    # 设置 threshold
    if args.threshold != None:
        zip_utils.threshold = args.threshold

    # 构建包
    pkg_path = args.package
    # 基本目录结构
    base_folder = 'upload'
    blocks_folder = os.path.join(base_folder, 'blocks')
    if not args.no_clean:
        if os.path.exists(base_folder):
            shutil.rmtree(base_folder)
    mkdirs(blocks_folder)

    if args.blocks_only:
        unpack_blocks_only(pkg_path, base_folder, blocks_folder, args.shrink_pkg_name)
    else:
        unpack_by_git(pkg_path, base_folder, blocks_folder, args)

    print('success')
