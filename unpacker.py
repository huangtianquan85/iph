#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import hashlib
import zip_shrink
import zip_repack
import json
import subprocess


# 获取 Shell 命令输出
def shell_output(command):
    try:
        return subprocess.check_output(command, shell=True).decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        return ''


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


if __name__ == '__main__':
    # 项目名称
    project_name = sys.argv[1]
    # 目标平台，Android/iOS
    platform = sys.argv[2]
    # 构建包
    pkg_path = sys.argv[3]

    # 获取 git 提交信息
    branch = shell_output('git rev-parse --abbrev-ref HEAD')
    git_version = shell_output('git rev-parse HEAD')[:8]
    author = shell_output('git --no-pager show -s --format="%an" HEAD')
    commit_time = shell_output('git --no-pager show -s --format="%cI" HEAD')
    msg = shell_output('git --no-pager show -s --format="%s" HEAD')

    commit = {
        "branch": branch,
        "short_id": git_version,
        'author': author,
        'commit_time': commit_time,
        "msg": msg,
        "icon": ""
    }

    '''
    目录结构
    upload
        last-<平台>-<项目>-<分之>.commit
        <平台>-<项目>-<分之>
            2022-01-01-<git_hash>.commit
            2022-01-01-<git_hash>.apk
            ...
        blocks
            <md5>
            ...
    '''

    # 各种路径
    base_folder = 'upload'
    blocks_folder = os.path.join(base_folder, 'blocks')
    # 平台-项目-分支
    ppb = '%s-%s-%s' % (platform, project_name, branch)
    index_folder = os.path.join(base_folder, ppb)
    # 日期-git_Hash
    date_hash = '%s-%s' % (commit_time[:10], git_version)
    commit_path = os.path.join(index_folder, date_hash + '.commit')
    shrink_pkg_path = os.path.join(
        index_folder, date_hash + os.path.splitext(pkg_path)[1])
    last_commit_path = os.path.join(base_folder, 'last-' + ppb + '.commit')
    # 测试文件
    tmp = os.path.join(base_folder, 'tmp')

    # 重建上传目录
    if os.path.exists(base_folder):
        shutil.rmtree(base_folder)
    os.makedirs(blocks_folder)
    os.makedirs(index_folder)

    def monitor(name, hash):
        if name == 'res/mipmap-xxhdpi-v4/app_icon.png':
            commit['icon'] = hash

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
    write_json(commit, commit_path)
    write_json(commit, last_commit_path)
    print('success')