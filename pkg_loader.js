const threshold = 4096;
const hash_len = 16;

function get_hash_str(buffer, offset) {
    const hash_view = new Uint8Array(buffer, offset, hash_len);
    return [...hash_view].map((x) => x.toString(16).padStart(2, "0")).join("");
}

class file {
    /*
    0   central file header signature   4 bytes  (0x02014b50)
    4   version made by                 2 bytes
    6   version needed to extract       2 bytes
    8   general purpose bit flag        2 bytes
    10  compression method              2 bytes
    12  last mod file time              2 bytes
    14  last mod file date              2 bytes
    16  crc-32                          4 bytes
    20  compressed size                 4 bytes  (压缩后大小)
    24  uncompressed size               4 bytes
    28  file name length                2 bytes  (文件名长度)
    30  extra field length              2 bytes  (扩展区长度)
    32  file comment length             2 bytes  (注释长度)
    34  disk number start               2 bytes
    36  internal file attributes        2 bytes
    38  external file attributes        4 bytes
    42  relative offset of local header 4 bytes  (文件存储区头结构偏移)

        file name (variable size)
        extra field (variable size)
        file comment (variable size)
    */

    constructor(buffer, offset) {
        this.buffer = buffer;

        // 头部固定数据段长度
        const fixed_len = 46;

        // 头结构视图
        const view = new DataView(buffer, offset, fixed_len);

        // 判断签名是否匹配，DataView Get 方法 true 为小端法
        this.match_sign = view.getInt32(0, true) === 0x02014b50;
        if (!this.match_sign) {
            return;
        }

        // 文件名长度
        let name_len = view.getInt16(28, true);
        // 文件名
        this.name = String.fromCharCode.apply(null, new Uint8Array(buffer, offset + fixed_len, name_len));
        // 计算本数据段总长，固定长度 + 文件名长度 + 扩展区长度 + 注释区长度
        this.info_len = fixed_len + name_len + view.getInt16(30, true) + view.getInt16(32, true);
        // 记录内容长度
        this.compressed_size = view.getInt32(20, true);

        // if (this.compressed_size > threshold) {
        //     console.log(this.compressed_size, this.name);
        // }

        // 内容 hash
        this.hash = "";

        // 文件区的头结构偏移
        this.header_offset = view.getInt32(42, true);
        // 文件区的头结构大小
        this.header_len = 0;
        // 内容
        this.data = null;
    }

    // 读取记录在存储区的文件内容 hash
    load_hash() {
        this.hash = get_hash_str(this.buffer, this.header_offset + this.header_len);
    }

    // 获取文件区文件头结构的长度
    parse_header_len() {
        /*
        Get local file header total length

        0   local file header signature     4 bytes  (0x04034b50)
        4   version needed to extract       2 bytes
        6   general purpose bit flag        2 bytes
        8   compression method              2 bytes
        10  last mod file time              2 bytes
        12  last mod file date              2 bytes
        14  crc-32                          4 bytes
        18  compressed size                 4 bytes
        22  uncompressed size               4 bytes
        26  file name length                2 bytes  (文件名长度)
        28  extra field length              2 bytes  (扩展区长度)

            file name (variable size)
            extra field (variable size)
        */
        let fixed_len = 30;
        const view = new DataView(this.buffer, this.header_offset, fixed_len);
        this.header_len = fixed_len + view.getInt16(26, true) + view.getInt16(28, true);
    }

    // 设置文件区文件头结构的真实偏移
    set_real_header_offset(offset) {
        this.header_offset = offset;
    }
}

const State = {
    Init: -1,
    CheckCache: 0,
    NeedDownload: 1,
    Downloading: 2,
    Success: 3,
    Fail: 4,
};

class file_loader {
    constructor(hash, size) {
        this.hash = hash;
        this.size = size;
        this.timeout = 0; // TODO
        this.state = State.Init;
        this.in_cache = true;
        this.progress = 0;
        this.checked_db = false;
        this.onloaded = [];
    }

    load_from_db() {
        this.state = State.CheckCache;
        idbKeyval.get(this.hash).then((data) => {
            if (data === undefined) {
                this.state = State.NeedDownload;
                this.in_cache = false;
            } else {
                this.loaded(data);
            }
        });
    }

    download() {
        this.state = State.Downloading;
        download("blocks/" + this.hash, (p) => {
            this.progress = p;
        })
            .then((data) => {
                this.insert_db(data);
            })
            .catch((error) => {
                console.log(error);
                this.state = State.Fail;
            });
    }

    insert_db(data) {
        idbKeyval
            .set(this.hash, data)
            .then(() => {
                this.loaded(data);
            })
            .catch((error) => {
                console.log(error);
                this.state = State.Fail;
            });
    }

    loaded(data) {
        for (const f of this.onloaded) {
            f.data = data;
        }
        this.state = State.Success;
    }
}

// 参考：https://zh.javascript.info/xmlhttprequest
function download(url, progress_callback) {
    return new Promise((resolve, reject) => {
        let xhr = new XMLHttpRequest();
        xhr.open("GET", url);
        xhr.responseType = "arraybuffer";
        xhr.send();

        xhr.onload = () => {
            if (xhr.status != 200) {
                reject(new Error(`Error ${xhr.status}: ${xhr.statusText}`));
                return;
            }

            resolve(xhr.response);
        };

        xhr.onerror = function () {
            reject(new Error("Network Error"));
        };

        xhr.onprogress = (event) => {
            progress_callback(event.loaded / event.total);
        };
    });
}

class zip_loader {
    constructor(url) {
        this.url = url;
        let arr = url.split("/");
        this.name = arr[arr.length - 1];
        this.shrink_data = null;
        this.shrink_data_progress = 0;
        this.origin_hash = "";
        this.files = [];
        this.file_loaders = [];
        this.download_queue = [];
        this.download_state = null;
        this.max_downloader = 5;
        this.ticker = null;
    }

    // 开始下载精简版本 zip
    start() {
        download(this.url, (p) => {
            this.shrink_data_progress = p;
        })
            .then((data) => {
                this.shrink_data = data;
                this.parse();
            })
            .catch((error) => {
                console.log(error);
                alert("download shrink package error: " + error);
            });
    }

    // 解析精简版本 zip
    parse() {
        let buffer = this.shrink_data;

        // 抽取写在文件末尾的原始文件 hash
        let end = buffer.byteLength - hash_len;
        this.origin_hash = get_hash_str(buffer, end);

        // 去掉末尾 hash 部分
        buffer = buffer.slice(0, end);
        this.shrink_data = buffer;

        // 开始解析
        let loaders = {};

        let dir = this.parse_EOCD(buffer);
        this.files = this.parse_directory(buffer, dir.offset, dir.size);

        // 抽出大小，用于修正精简版 zip 中文件头的偏移
        let ex_size = 0;
        // 遍历所有文件待处理文件
        for (const f of this.files) {
            // 计算头结构修正偏移
            f.set_real_header_offset(f.header_offset - ex_size);
            // 获取头结构大小
            f.parse_header_len();

            // 加载内容 hash
            f.load_hash();

            // 根据内容 hash 创建下载器（ zip 内相同的文件只会下载一份 ）
            if (!loaders.hasOwnProperty(f.hash)) {
                loaders[f.hash] = new file_loader(f.hash, f.compressed_size);
            }
            loaders[f.hash].onloaded.push(f);

            // 修正头结构偏移
            ex_size += f.compressed_size - hash_len;
        }

        // 转为列表
        this.file_loaders = Object.values(loaders);

        // 开始批量加载，每秒 25 帧
        this.ticker = setInterval(() => {
            this.update();
        }, 40);
    }

    // 解析中央目录结束标记，返回中央目录偏移和大小
    parse_EOCD(buffer) {
        /*
        重点: **中央目录中文件信息是连续的，且其后紧跟结束标记（zip64 除外，本项目暂不支持 zip64）**
        因为中央目录结束标记中记录的中央目录偏移是针对文件头的编译
        所以精简版 zip 这个偏移无法命中，也无法计算（需要先解析中央目录）
        只能这样计算: 中央目录结束标记偏移 - 目录大小

        End of central directory record

        0   end of central dir signature    4 bytes  (0x06054b50)
        4   number of this disk             2 bytes
        6   number of the disk with the
            start of the central directory  2 bytes
        8   total number of entries in the
            central directory on this disk  2 bytes
        10  total number of entries in
            the central directory           2 bytes
        12  size of the central directory   4 bytes  (中央目录大小)
        16  offset of start of central
            directory with respect to
            the starting disk number        4 bytes
        20  .ZIP file comment length        2 bytes
        22  .ZIP file comment               (variable size)
        */

        // EOCD固定数据段长度
        const fixed_len = 22;
        // 起始搜索位置近似值
        let offset = buffer.byteLength - fixed_len;
        while (offset > 0) {
            const view = new DataView(buffer, offset, fixed_len);
            if (view.getInt32(0, true) !== 0x06054b50) {
                offset -= 1;
                continue;
            }
            let size = view.getInt32(12, true);
            return {
                size: size,
                offset: offset - size,
            };
        }
        return null;
    }

    // 遍历中央目录中的所有文件信息
    parse_directory(buffer, dir_offset, dir_size) {
        let file_infos = [];
        let offset = dir_offset;
        let end = dir_offset + dir_size;
        while (offset < end) {
            let f = new file(buffer, offset);
            // 过滤掉小于 4k 的文件
            if (f.compressed_size > threshold) {
                file_infos.push(f);
            }
            offset += f.info_len;
        }

        // 按偏移量排序（中央目录不保证顺序，但不会有两个文件共用存储，结构上就不支持）
        /*
        From Wikipedia Zip Format:
        The order of the file entries in the central directory 
        need not coincide with the order of file entries in the archive
        */
        file_infos.sort((a, b) => a.header_offset - b.header_offset);
        return file_infos;
    }

    // 扫描下载/加载状态
    update() {
        let need_download = [];
        // loaded + error 和 file_loaders.length 比较来确定加载总进度
        let loaded = 0;
        let error = 0;
        // 控制下载线程数
        let downloading = 0;
        for (const l of this.file_loaders) {
            if (l.state === State.Init) {
                l.load_from_db();
            } else if (l.state === State.NeedDownload) {
                need_download.push(l);
            } else if (l.state === State.Downloading) {
                downloading++;
            } else if (l.state === State.Success) {
                loaded++;
            } else if (l.state === State.Fail) {
                error++;
            }
        }

        // 添加下载
        for (let i = 0; i < Math.min(this.max_downloader - downloading, need_download.length); i++) {
            need_download[i].download();
            this.download_queue.push(need_download[i]);
        }

        // 清理下载队列
        this.download_queue = this.download_queue.filter((l) => l.state === State.Downloading);

        // 刷新状态
        this.update_download_state();

        // 下载完成, TODO: retry when error
        if (loaded + error === this.file_loaders.length) {
            console.log("all done");
            clearInterval(this.ticker);
            this.repack();
        }
    }

    update_download_state() {
        let s = {
            total_num: 0,
            total_size: 0,
            downloaded_num: 0,
            downloaded_size: 0,
            error_num: 0,
        };
        for (const l of this.file_loaders) {
            if (!l.in_cache) {
                s.total_num++;
                s.total_size += l.size;
                s.downloaded_size += l.size * l.progress;
                if (l.state === State.Success) {
                    s.downloaded_num++;
                } else if (l.state === State.Fail) {
                    s.error_num++;
                }
            }
        }
        this.download_state = s;
    }

    // 重组 zip 包
    repack() {
        var bytes = [];
        var hash = md5.create();

        function append(byte_range) {
            bytes.push(byte_range);
            hash.update(byte_range);
        }

        // 光标，记录上一次处理到的位置
        let cursor = 0;
        // 遍历所有文件待处理文件
        for (const f of this.files) {
            // 写入上一个处理位置到此头结构结尾的数据
            let offset = f.header_offset + f.header_len;
            append(new Uint8Array(f.buffer, cursor, offset - cursor));

            // 写入文件内容
            append(new Uint8Array(f.data));

            // 光标置于文件内容区末尾（精简版只需要跳过 hash 的长度）
            cursor = offset + hash_len;
        }

        append(new Uint8Array(this.shrink_data, cursor));

        console.log(hash.hex());
        if (this.origin_hash !== hash.hex()) {
            alert("hash check error");
            return;
        }

        let fileBlob = new Blob(bytes);
        let a = document.createElement("a");
        a.download = this.url;
        a.href = URL.createObjectURL(fileBlob);
        a.style.display = "none";
        document.body.appendChild(a);
        a.click();
        a.remove();
    }
}
